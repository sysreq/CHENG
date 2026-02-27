// ============================================================================
// CHENG — Mesh parser smoke tests
// Tier 1: always run pre-commit (< 1s each)
//
// Covers: binary mesh frame parsing — the core WebSocket binary protocol.
// Tests that the frame parser handles valid input and error frames correctly.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { parseMeshFrame } from '@/lib/meshParser';
import type { MeshFrame, ErrorFrame } from '@/lib/meshParser';

/** Build a minimal valid mesh frame ArrayBuffer. */
function buildMeshFrame(vertexCount: number, faceCount: number): ArrayBuffer {
  const verticesBytes = vertexCount * 3 * 4;
  const normalsBytes = vertexCount * 3 * 4;
  const facesBytes = faceCount * 3 * 4;

  const trailer = JSON.stringify({
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
  });
  const trailerBytes = new TextEncoder().encode(trailer);

  const headerSize = 12;
  const buffer = new ArrayBuffer(headerSize + verticesBytes + normalsBytes + facesBytes + trailerBytes.length);
  const view = new DataView(buffer);

  view.setUint32(0, 0x00000001, true); // MSG_TYPE_MESH
  view.setUint32(4, vertexCount, true);
  view.setUint32(8, faceCount, true);

  new Uint8Array(buffer, headerSize + verticesBytes + normalsBytes + facesBytes).set(trailerBytes);
  return buffer;
}

/** Build a minimal error frame ArrayBuffer. */
function buildErrorFrame(error: string, detail: string): ArrayBuffer {
  const json = JSON.stringify({ error, detail, field: null });
  const jsonBytes = new TextEncoder().encode(json);
  const buffer = new ArrayBuffer(4 + jsonBytes.length);
  new DataView(buffer).setUint32(0, 0x00000002, true);
  new Uint8Array(buffer, 4).set(jsonBytes);
  return buffer;
}

describe('[smoke] meshParser', () => {
  it('parses a valid mesh frame — correct message type', () => {
    const buffer = buildMeshFrame(3, 1);
    const frame = parseMeshFrame(buffer);
    expect(frame.type).toBe(0x01);
  });

  it('parses a valid mesh frame — vertex and face counts', () => {
    const buffer = buildMeshFrame(6, 2);
    const frame = parseMeshFrame(buffer) as MeshFrame;
    expect(frame.vertexCount).toBe(6);
    expect(frame.faceCount).toBe(2);
  });

  it('parses a valid mesh frame — typed arrays', () => {
    const buffer = buildMeshFrame(4, 2);
    const frame = parseMeshFrame(buffer) as MeshFrame;
    expect(frame.vertices).toBeInstanceOf(Float32Array);
    expect(frame.normals).toBeInstanceOf(Float32Array);
    expect(frame.faces).toBeInstanceOf(Uint32Array);
    expect(frame.vertices.length).toBe(12); // 4 * 3
    expect(frame.faces.length).toBe(6);     // 2 * 3
  });

  it('parses an error frame — correct message type', () => {
    const buffer = buildErrorFrame('generation_error', 'Test error');
    const frame = parseMeshFrame(buffer);
    expect(frame.type).toBe(0x02);
  });

  it('parses an error frame — error and detail fields', () => {
    const buffer = buildErrorFrame('validation_error', 'Design is invalid');
    const frame = parseMeshFrame(buffer) as ErrorFrame;
    expect(frame.error).toBe('validation_error');
    expect(frame.detail).toBe('Design is invalid');
  });
});
