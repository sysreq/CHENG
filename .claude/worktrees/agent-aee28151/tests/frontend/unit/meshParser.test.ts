// ============================================================================
// CHENG — Binary mesh frame parser unit tests
// ============================================================================

import { describe, it, expect } from 'vitest';
import { parseMeshFrame } from '@/lib/meshParser';
import type { MeshFrame, ErrorFrame } from '@/lib/meshParser';

/**
 * Build a valid mesh frame ArrayBuffer with the given vertex/face counts
 * and a JSON trailer containing derived values and validation warnings.
 */
function buildMeshFrame(
  vertexCount: number,
  faceCount: number,
  trailer?: Record<string, unknown>,
): ArrayBuffer {
  const verticesBytes = vertexCount * 3 * 4;
  const normalsBytes = vertexCount * 3 * 4;
  const facesBytes = faceCount * 3 * 4;

  const trailerStr = JSON.stringify(
    trailer ?? {
      derived: {
        tipChordMm: 200,
        wingAreaCm2: 2400,
        aspectRatio: 6.0,
        meanAeroChordMm: 200,
        taperRatio: 1.0,
        estimatedCgMm: 50,
        minFeatureThicknessMm: 0.8,
        wallThicknessMm: 1.2,
      },
      validation: [],
    },
  );
  const trailerBytes = new TextEncoder().encode(trailerStr);

  const headerSize = 12;
  const totalSize = headerSize + verticesBytes + normalsBytes + facesBytes + trailerBytes.length;
  const buffer = new ArrayBuffer(totalSize);
  const view = new DataView(buffer);

  // Header
  view.setUint32(0, 0x00000001, true); // MSG_TYPE_MESH
  view.setUint32(4, vertexCount, true);
  view.setUint32(8, faceCount, true);

  // Fill vertices with simple data
  const verts = new Float32Array(buffer, headerSize, vertexCount * 3);
  for (let i = 0; i < vertexCount * 3; i++) verts[i] = i * 1.0;

  // Fill normals
  const norms = new Float32Array(buffer, headerSize + verticesBytes, vertexCount * 3);
  for (let i = 0; i < vertexCount * 3; i++) norms[i] = 0;

  // Fill faces with sequential indices
  const faces = new Uint32Array(buffer, headerSize + verticesBytes + normalsBytes, faceCount * 3);
  for (let i = 0; i < faceCount * 3; i++) faces[i] = i % vertexCount;

  // Write trailer
  const trailerTarget = new Uint8Array(buffer, headerSize + verticesBytes + normalsBytes + facesBytes);
  trailerTarget.set(trailerBytes);

  return buffer;
}

/** Build an error frame ArrayBuffer. */
function buildErrorFrame(error: string, detail: string, field?: string): ArrayBuffer {
  const json = JSON.stringify({ error, detail, field: field ?? null });
  const jsonBytes = new TextEncoder().encode(json);
  const buffer = new ArrayBuffer(4 + jsonBytes.length);
  new DataView(buffer).setUint32(0, 0x00000002, true);
  new Uint8Array(buffer, 4).set(jsonBytes);
  return buffer;
}

describe('parseMeshFrame', () => {
  it('parses a valid mesh frame with correct header values', () => {
    const buffer = buildMeshFrame(4, 2);
    const frame = parseMeshFrame(buffer);

    expect(frame.type).toBe(0x01);
    const mesh = frame as MeshFrame;
    expect(mesh.vertexCount).toBe(4);
    expect(mesh.faceCount).toBe(2);
    expect(mesh.vertices).toBeInstanceOf(Float32Array);
    expect(mesh.vertices.length).toBe(12); // 4 * 3
    expect(mesh.normals.length).toBe(12);
    expect(mesh.faces).toBeInstanceOf(Uint32Array);
    expect(mesh.faces.length).toBe(6); // 2 * 3
  });

  it('extracts Float32Array vertex positions correctly', () => {
    const buffer = buildMeshFrame(3, 1);
    const frame = parseMeshFrame(buffer) as MeshFrame;

    // We filled vertices with sequential floats: 0, 1, 2, 3, ...
    expect(frame.vertices[0]).toBeCloseTo(0.0);
    expect(frame.vertices[1]).toBeCloseTo(1.0);
    expect(frame.vertices[2]).toBeCloseTo(2.0);
  });

  it('parses derived values from JSON trailer', () => {
    const buffer = buildMeshFrame(1, 1, {
      derived: {
        tipChordMm: 150,
        wingAreaCm2: 1800,
        aspectRatio: 5.5,
        meanAeroChordMm: 160,
        taperRatio: 0.8,
        estimatedCgMm: 40,
        minFeatureThicknessMm: 0.6,
        wallThicknessMm: 1.0,
      },
      validation: [{ id: 'V01', level: 'warn', message: 'High AR', fields: ['wingSpan'] }],
    });

    const frame = parseMeshFrame(buffer) as MeshFrame;
    expect(frame.derived.tipChordMm).toBe(150);
    expect(frame.derived.wingAreaCm2).toBe(1800);
    expect(frame.validation).toHaveLength(1);
    expect(frame.validation[0]!.id).toBe('V01');
  });

  it('parses componentRanges from trailer when present', () => {
    const buffer = buildMeshFrame(6, 4, {
      derived: {
        tipChordMm: 200, wingAreaCm2: 2400, aspectRatio: 6,
        meanAeroChordMm: 200, taperRatio: 1, estimatedCgMm: 50,
        minFeatureThicknessMm: 0.8, wallThicknessMm: 1.2,
      },
      validation: [],
      componentRanges: { fuselage: [0, 2], wing: [2, 3], tail: [3, 4] },
    });

    const frame = parseMeshFrame(buffer) as MeshFrame;
    expect(frame.componentRanges).toBeDefined();
    expect(frame.componentRanges!.fuselage).toEqual([0, 2]);
    expect(frame.componentRanges!.wing).toEqual([2, 3]);
    expect(frame.componentRanges!.tail).toEqual([3, 4]);
  });

  it('handles empty mesh frame (0 vertices, 0 faces)', () => {
    const buffer = buildMeshFrame(0, 0);
    const frame = parseMeshFrame(buffer) as MeshFrame;
    expect(frame.vertexCount).toBe(0);
    expect(frame.faceCount).toBe(0);
    expect(frame.vertices.length).toBe(0);
    expect(frame.faces.length).toBe(0);
  });

  it('parses error frame correctly', () => {
    const buffer = buildErrorFrame('validation_error', 'wingSpan out of range', 'wingSpan');
    const frame = parseMeshFrame(buffer);

    expect(frame.type).toBe(0x02);
    const err = frame as ErrorFrame;
    expect(err.error).toBe('validation_error');
    expect(err.detail).toBe('wingSpan out of range');
    expect(err.field).toBe('wingSpan');
  });

  it('throws on buffer too small', () => {
    const tiny = new ArrayBuffer(2);
    expect(() => parseMeshFrame(tiny)).toThrow('Buffer too small');
  });

  it('throws on unknown message type', () => {
    const buffer = new ArrayBuffer(12);
    new DataView(buffer).setUint32(0, 0x000000FF, true);
    expect(() => parseMeshFrame(buffer)).toThrow('Unknown message type');
  });
});
