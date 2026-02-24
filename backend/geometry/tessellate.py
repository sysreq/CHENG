"""Mesh tessellation utilities for preview (WebSocket) and export (STL).

MeshData is a pure-Python/numpy dataclass usable without CadQuery.
The tessellate_for_preview() and tessellate_for_export() functions
require CadQuery at runtime (guarded import).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    import cadquery as cq


# ---------------------------------------------------------------------------
# MeshData
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MeshData:
    """Tessellated mesh data for WebSocket binary transport.

    Contains the raw vertex, normal, and face data that gets packed into the
    binary WebSocket frame (message type 0x01) per spec Section 6.2.

    Layout in the binary frame:
      - vertices: N x 3 float32 array of (x, y, z) positions
      - normals:  N x 3 float32 array of (nx, ny, nz) per-vertex normals
      - faces:    M x 3 uint32 array of triangle vertex indices

    Attributes:
        vertices: Shape (N, 3), dtype float32.  Vertex positions in mm.
        normals:  Shape (N, 3), dtype float32.  Unit-length per-vertex normals.
        faces:    Shape (M, 3), dtype uint32.  Triangle indices into vertices/normals.
    """

    vertices: NDArray[np.float32]   # shape (N, 3)
    normals: NDArray[np.float32]    # shape (N, 3)
    faces: NDArray[np.uint32]       # shape (M, 3)

    @property
    def vertex_count(self) -> int:
        """Number of vertices."""
        return self.vertices.shape[0]

    @property
    def face_count(self) -> int:
        """Number of triangular faces."""
        return self.faces.shape[0]

    def to_binary_frame(self) -> bytes:
        """Pack into the WebSocket binary frame format (spec Section 6.2).

        Returns a bytes object with layout:
          [msg_type: uint32][vertex_count: uint32][face_count: uint32]
          [vertices: N*12 bytes][normals: N*12 bytes][faces: M*12 bytes]

        The JSON trailer (derived values + validation) is NOT included here;
        the WebSocket handler appends it separately.
        """
        msg_type = np.uint32(0x01)
        vert_count = np.uint32(self.vertex_count)
        face_count = np.uint32(self.face_count)

        header = struct.pack("<III", int(msg_type), int(vert_count), int(face_count))

        vert_bytes = self.vertices.astype(np.float32).tobytes()
        norm_bytes = self.normals.astype(np.float32).tobytes()
        face_bytes = self.faces.astype(np.uint32).tobytes()

        return header + vert_bytes + norm_bytes + face_bytes


# ---------------------------------------------------------------------------
# Tessellation functions (require CadQuery at runtime)
# ---------------------------------------------------------------------------


def tessellate_for_preview(solid: cq.Workplane, tolerance: float = 0.5) -> MeshData:
    """Tessellate a CadQuery solid into triangle mesh for WebSocket preview.

    Uses coarser tolerance than export for fast transfer.  Default 0.5 mm
    produces ~20k-50k triangles (~1-3 MB binary) for a 1000 mm aircraft.

    Args:
        solid:     CadQuery Workplane containing one or more solids.
        tolerance: Max chordal deviation in mm.  Default 0.5 mm for preview.

    Returns:
        MeshData with float32 vertices/normals and uint32 face indices.
    """
    import cadquery as cq  # noqa: F811 -- runtime import

    return _tessellate_workplane(solid, tolerance)


def tessellate_for_export(solid: cq.Workplane, tolerance: float = 0.1) -> bytes:
    """Tessellate a CadQuery solid into binary STL for file export.

    Uses finer tolerance for dimensional accuracy.  Output must be watertight
    (acceptance criterion D1: zero errors in PrusaSlicer/Cura/Bambu Studio).

    Binary STL format: 80-byte header + 4-byte triangle count + 50 bytes/triangle.

    Args:
        solid:     CadQuery Workplane containing a single solid.
        tolerance: Max chordal deviation in mm.  Default 0.1 mm for export quality.

    Returns:
        Binary STL file content as bytes.
    """
    import cadquery as cq  # noqa: F811 -- runtime import

    mesh = _tessellate_workplane(solid, tolerance)
    return _mesh_to_binary_stl(mesh)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tessellate_workplane(solid: cq.Workplane, tolerance: float) -> MeshData:
    """Extract triangle mesh from a CadQuery Workplane.

    Uses the OCCT tessellation via CadQuery's ``tessellate()`` method on each
    solid.  Merges all solids in the workplane into a single mesh.
    """
    all_vertices: list[tuple[float, float, float]] = []
    all_faces: list[tuple[int, int, int]] = []

    offset = 0

    for shape in solid.objects:
        # CadQuery Shape.tessellate returns (vertices, faces)
        verts, faces = shape.tessellate(tolerance)
        for v in verts:
            all_vertices.append((v.x, v.y, v.z))
        for f in faces:
            all_faces.append((f[0] + offset, f[1] + offset, f[2] + offset))
        offset += len(verts)

    if not all_vertices:
        # Return empty mesh
        return MeshData(
            vertices=np.zeros((0, 3), dtype=np.float32),
            normals=np.zeros((0, 3), dtype=np.float32),
            faces=np.zeros((0, 3), dtype=np.uint32),
        )

    vertices_np = np.array(all_vertices, dtype=np.float32)
    faces_np = np.array(all_faces, dtype=np.uint32)

    # Compute per-vertex normals from face normals (area-weighted average)
    normals_np = _compute_vertex_normals(vertices_np, faces_np)

    return MeshData(
        vertices=vertices_np,
        normals=normals_np,
        faces=faces_np,
    )


def _compute_vertex_normals(
    vertices: NDArray[np.float32],
    faces: NDArray[np.uint32],
) -> NDArray[np.float32]:
    """Compute per-vertex normals by averaging adjacent face normals.

    Uses area-weighted averaging: each face's contribution to a vertex normal
    is proportional to the face area (implicit in the cross product magnitude).
    """
    normals = np.zeros_like(vertices)

    if faces.shape[0] == 0:
        return normals

    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]

    # Face normals (not normalised -- magnitude = 2 * area)
    edge1 = v1 - v0
    edge2 = v2 - v0
    face_normals = np.cross(edge1, edge2)

    # Accumulate face normals to each vertex
    for i in range(3):
        np.add.at(normals, faces[:, i], face_normals)

    # Normalise per-vertex normals
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    lengths = np.maximum(lengths, 1e-10)  # avoid division by zero
    normals = normals / lengths

    return normals.astype(np.float32)


def _mesh_to_binary_stl(mesh: MeshData) -> bytes:
    """Convert MeshData to binary STL format.

    Binary STL layout:
      - 80-byte header (ASCII, zero-padded)
      - 4-byte uint32: number of triangles
      - For each triangle (50 bytes):
        - 12 bytes: face normal (3 x float32)
        - 36 bytes: 3 vertices (3 x 3 x float32)
        - 2 bytes: attribute byte count (0)
    """
    header = b"CHENG Parametric RC Plane Generator - Binary STL"
    header = header.ljust(80, b"\x00")

    num_triangles = mesh.face_count
    count_bytes = struct.pack("<I", num_triangles)

    triangle_data = bytearray()
    for i in range(num_triangles):
        i0, i1, i2 = mesh.faces[i]
        v0 = mesh.vertices[i0]
        v1 = mesh.vertices[i1]
        v2 = mesh.vertices[i2]

        # Compute face normal
        edge1 = v1 - v0
        edge2 = v2 - v0
        normal = np.cross(edge1, edge2)
        length = np.linalg.norm(normal)
        if length > 1e-10:
            normal = normal / length

        # Pack: normal (3 floats) + 3 vertices (9 floats) + attribute (uint16)
        triangle_data.extend(struct.pack("<fff", *normal))
        triangle_data.extend(struct.pack("<fff", *v0))
        triangle_data.extend(struct.pack("<fff", *v1))
        triangle_data.extend(struct.pack("<fff", *v2))
        triangle_data.extend(struct.pack("<H", 0))

    return header + count_bytes + bytes(triangle_data)
