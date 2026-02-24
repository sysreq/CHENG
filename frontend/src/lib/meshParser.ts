// ============================================================================
// CHENG — WebSocket Binary Frame Parser
// Spec: implementation_guide.md §5 (Binary Parser)
// ============================================================================

import * as THREE from 'three';
import type { DerivedValues, ValidationWarning } from '@/types/design';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MSG_TYPE_MESH = 0x00000001;
const MSG_TYPE_ERROR = 0x00000002;

/** Minimum header size: msgType (4) + vertexCount (4) + faceCount (4) = 12 bytes */
const MESH_HEADER_SIZE = 12;

/** Minimum error frame size: msgType (4) + at least 2 bytes JSON "{}" */
const ERROR_MIN_SIZE = 6;

// ---------------------------------------------------------------------------
// Frame Types
// ---------------------------------------------------------------------------

/** Parsed mesh update frame from WebSocket binary protocol. */
export interface MeshFrame {
  type: 0x01;
  vertexCount: number;
  faceCount: number;
  vertices: Float32Array;
  normals: Float32Array;
  faces: Uint32Array;
  derived: DerivedValues;
  validation: ValidationWarning[];
}

/** Parsed error frame from WebSocket binary protocol. */
export interface ErrorFrame {
  type: 0x02;
  error: string;
  detail: string;
  field: string | null;
}

/** Discriminated union of all parsed frame types. */
export type ParsedFrame = MeshFrame | ErrorFrame;

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------

/**
 * Parse a binary WebSocket frame from the CHENG backend.
 *
 * Mesh update (0x01) layout — all little-endian:
 *   [0..4]   uint32 message type
 *   [4..8]   uint32 vertex count (N)
 *   [8..12]  uint32 face count (M)
 *   [12..]   float32[N*3] vertex positions
 *   [..]     float32[N*3] vertex normals
 *   [..]     uint32[M*3]  face indices
 *   [..]     UTF-8 JSON   trailer {derived, validation}
 *
 * Error (0x02) layout:
 *   [0..4]   uint32 message type
 *   [4..]    UTF-8 JSON   {error, detail, field}
 *
 * @throws Error if buffer too small or unknown message type.
 */
export function parseMeshFrame(data: ArrayBuffer): ParsedFrame {
  if (data.byteLength < 4) {
    throw new Error(`Buffer too small: ${data.byteLength} bytes (minimum 4)`);
  }

  const view = new DataView(data);
  const msgType = view.getUint32(0, true); // little-endian

  if (msgType === MSG_TYPE_MESH) {
    return parseMeshUpdate(data, view);
  } else if (msgType === MSG_TYPE_ERROR) {
    return parseErrorFrame(data);
  } else {
    throw new Error(`Unknown message type: 0x${msgType.toString(16).padStart(8, '0')}`);
  }
}

/**
 * Parse a mesh update frame (type 0x01).
 */
function parseMeshUpdate(data: ArrayBuffer, view: DataView): MeshFrame {
  if (data.byteLength < MESH_HEADER_SIZE) {
    throw new Error(
      `Mesh frame too small: ${data.byteLength} bytes (minimum ${MESH_HEADER_SIZE})`,
    );
  }

  const vertexCount = view.getUint32(4, true);
  const faceCount = view.getUint32(8, true);

  // Calculate byte offsets for each section
  const verticesByteOffset = MESH_HEADER_SIZE;
  const verticesByteLength = vertexCount * 3 * 4; // float32 = 4 bytes

  const normalsByteOffset = verticesByteOffset + verticesByteLength;
  const normalsByteLength = vertexCount * 3 * 4;

  const facesByteOffset = normalsByteOffset + normalsByteLength;
  const facesByteLength = faceCount * 3 * 4; // uint32 = 4 bytes

  const trailerByteOffset = facesByteOffset + facesByteLength;

  // Validate buffer has enough data for mesh arrays
  if (data.byteLength < trailerByteOffset) {
    throw new Error(
      `Mesh frame truncated: expected at least ${trailerByteOffset} bytes for ` +
        `${vertexCount} vertices and ${faceCount} faces, got ${data.byteLength}`,
    );
  }

  // Create typed array views (zero-copy from the ArrayBuffer)
  const vertices = new Float32Array(data, verticesByteOffset, vertexCount * 3);
  const normals = new Float32Array(data, normalsByteOffset, vertexCount * 3);
  const faces = new Uint32Array(data, facesByteOffset, faceCount * 3);

  // Parse JSON trailer (derived values + validation warnings)
  let derived: DerivedValues;
  let validation: ValidationWarning[];

  if (trailerByteOffset < data.byteLength) {
    const trailerBytes = new Uint8Array(data, trailerByteOffset);
    const trailerJson = new TextDecoder().decode(trailerBytes);
    const trailer = JSON.parse(trailerJson) as {
      derived: DerivedValues;
      validation: ValidationWarning[];
    };
    derived = trailer.derived;
    validation = trailer.validation;
  } else {
    // No trailer — provide empty defaults
    derived = {
      tipChordMm: 0,
      wingAreaCm2: 0,
      aspectRatio: 0,
      meanAeroChordMm: 0,
      taperRatio: 0,
      estimatedCgMm: 0,
      minFeatureThicknessMm: 0,
      wallThicknessMm: 0,
    };
    validation = [];
  }

  return {
    type: 0x01,
    vertexCount,
    faceCount,
    vertices,
    normals,
    faces,
    derived,
    validation,
  };
}

/**
 * Parse an error frame (type 0x02).
 */
function parseErrorFrame(data: ArrayBuffer): ErrorFrame {
  if (data.byteLength < ERROR_MIN_SIZE) {
    throw new Error(
      `Error frame too small: ${data.byteLength} bytes (minimum ${ERROR_MIN_SIZE})`,
    );
  }

  const jsonBytes = new Uint8Array(data, 4); // skip msgType uint32
  const jsonString = new TextDecoder().decode(jsonBytes);
  const parsed = JSON.parse(jsonString) as {
    error: string;
    detail: string;
    field?: string | null;
  };

  return {
    type: 0x02,
    error: parsed.error,
    detail: parsed.detail,
    field: parsed.field ?? null,
  };
}

// ---------------------------------------------------------------------------
// Three.js BufferGeometry Converter
// ---------------------------------------------------------------------------

/**
 * Create a Three.js BufferGeometry from a parsed MeshFrame.
 *
 * Uses Float32Arrays directly as buffer attributes (zero-copy from the
 * WebSocket ArrayBuffer). Computes bounding box and sphere for frustum
 * culling.
 *
 * Caller is responsible for disposal when geometry is replaced (call
 * geometry.dispose()).
 */
export function createBufferGeometry(frame: MeshFrame): THREE.BufferGeometry {
  const geometry = new THREE.BufferGeometry();

  // Set vertex positions — zero-copy from the parsed Float32Array
  geometry.setAttribute(
    'position',
    new THREE.BufferAttribute(frame.vertices, 3),
  );

  // Set vertex normals — zero-copy from the parsed Float32Array
  geometry.setAttribute(
    'normal',
    new THREE.BufferAttribute(frame.normals, 3),
  );

  // Set face indices
  geometry.setIndex(new THREE.BufferAttribute(frame.faces, 1));

  // Compute bounding volumes for frustum culling
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();

  return geometry;
}
