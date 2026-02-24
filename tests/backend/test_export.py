"""Tests for the export pipeline -- things that don't require CadQuery.

These tests cover:
- SectionPart dataclass creation
- Manifest generation
- Assembly notes generation
- MeshData binary frame serialization
"""

from __future__ import annotations

import struct

import numpy as np
import pytest

from backend.geometry.tessellate import MeshData


# ===================================================================
# MeshData tests
# ===================================================================


class TestMeshData:
    """Tests for MeshData dataclass and binary frame serialization."""

    @pytest.fixture
    def simple_mesh(self) -> MeshData:
        """A simple triangle mesh (one triangle)."""
        vertices = np.array(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            dtype=np.float32,
        )
        normals = np.array(
            [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
            dtype=np.float32,
        )
        faces = np.array([[0, 1, 2]], dtype=np.uint32)
        return MeshData(vertices=vertices, normals=normals, faces=faces)

    @pytest.fixture
    def cube_mesh(self) -> MeshData:
        """A simple cube mesh (8 vertices, 12 triangles)."""
        vertices = np.array(
            [
                [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
            ],
            dtype=np.float32,
        )
        normals = np.zeros((8, 3), dtype=np.float32)
        normals[:, 2] = 1.0  # simplified normals
        faces = np.array(
            [
                [0, 1, 2], [0, 2, 3],  # bottom
                [4, 6, 5], [4, 7, 6],  # top
                [0, 4, 5], [0, 5, 1],  # front
                [2, 6, 7], [2, 7, 3],  # back
                [0, 3, 7], [0, 7, 4],  # left
                [1, 5, 6], [1, 6, 2],  # right
            ],
            dtype=np.uint32,
        )
        return MeshData(vertices=vertices, normals=normals, faces=faces)

    def test_vertex_count(self, simple_mesh: MeshData) -> None:
        """vertex_count should match array length."""
        assert simple_mesh.vertex_count == 3

    def test_face_count(self, simple_mesh: MeshData) -> None:
        """face_count should match array length."""
        assert simple_mesh.face_count == 1

    def test_cube_counts(self, cube_mesh: MeshData) -> None:
        """Cube should have 8 vertices and 12 faces."""
        assert cube_mesh.vertex_count == 8
        assert cube_mesh.face_count == 12

    def test_binary_frame_header(self, simple_mesh: MeshData) -> None:
        """Binary frame should start with correct header."""
        frame = simple_mesh.to_binary_frame()

        # Parse header: msg_type, vertex_count, face_count
        msg_type, vert_count, face_count = struct.unpack_from("<III", frame, 0)
        assert msg_type == 0x01
        assert vert_count == 3
        assert face_count == 1

    def test_binary_frame_size(self, simple_mesh: MeshData) -> None:
        """Binary frame size should match expected layout."""
        frame = simple_mesh.to_binary_frame()

        # Header: 3 * 4 = 12 bytes
        # Vertices: 3 * 3 * 4 = 36 bytes
        # Normals: 3 * 3 * 4 = 36 bytes
        # Faces: 1 * 3 * 4 = 12 bytes
        expected_size = 12 + 36 + 36 + 12
        assert len(frame) == expected_size

    def test_binary_frame_cube_size(self, cube_mesh: MeshData) -> None:
        """Cube binary frame size check."""
        frame = cube_mesh.to_binary_frame()

        # Header: 12 bytes
        # Vertices: 8 * 3 * 4 = 96 bytes
        # Normals: 8 * 3 * 4 = 96 bytes
        # Faces: 12 * 3 * 4 = 144 bytes
        expected_size = 12 + 96 + 96 + 144
        assert len(frame) == expected_size

    def test_binary_frame_roundtrip(self, simple_mesh: MeshData) -> None:
        """Vertices in the binary frame should match the original data."""
        frame = simple_mesh.to_binary_frame()

        # Skip header (12 bytes), read vertices
        offset = 12
        n_verts = simple_mesh.vertex_count
        vert_bytes = frame[offset : offset + n_verts * 12]
        vertices = np.frombuffer(vert_bytes, dtype=np.float32).reshape(-1, 3)

        np.testing.assert_array_almost_equal(vertices, simple_mesh.vertices)

    def test_binary_frame_normals_roundtrip(self, simple_mesh: MeshData) -> None:
        """Normals in the binary frame should match the original data."""
        frame = simple_mesh.to_binary_frame()

        offset = 12 + simple_mesh.vertex_count * 12
        n_verts = simple_mesh.vertex_count
        norm_bytes = frame[offset : offset + n_verts * 12]
        normals = np.frombuffer(norm_bytes, dtype=np.float32).reshape(-1, 3)

        np.testing.assert_array_almost_equal(normals, simple_mesh.normals)

    def test_binary_frame_faces_roundtrip(self, simple_mesh: MeshData) -> None:
        """Faces in the binary frame should match the original data."""
        frame = simple_mesh.to_binary_frame()

        vert_offset = 12
        norm_offset = vert_offset + simple_mesh.vertex_count * 12
        face_offset = norm_offset + simple_mesh.vertex_count * 12
        face_bytes = frame[face_offset : face_offset + simple_mesh.face_count * 12]
        faces = np.frombuffer(face_bytes, dtype=np.uint32).reshape(-1, 3)

        np.testing.assert_array_equal(faces, simple_mesh.faces)

    def test_empty_mesh(self) -> None:
        """Empty mesh should produce a valid (minimal) binary frame."""
        mesh = MeshData(
            vertices=np.zeros((0, 3), dtype=np.float32),
            normals=np.zeros((0, 3), dtype=np.float32),
            faces=np.zeros((0, 3), dtype=np.uint32),
        )
        assert mesh.vertex_count == 0
        assert mesh.face_count == 0

        frame = mesh.to_binary_frame()
        assert len(frame) == 12  # header only

        msg_type, vert_count, face_count = struct.unpack_from("<III", frame, 0)
        assert msg_type == 0x01
        assert vert_count == 0
        assert face_count == 0

    def test_frozen_dataclass(self, simple_mesh: MeshData) -> None:
        """MeshData should be frozen (immutable)."""
        with pytest.raises(AttributeError):
            simple_mesh.vertices = np.zeros((1, 3), dtype=np.float32)  # type: ignore[misc]


# ===================================================================
# Binary STL helper tests
# ===================================================================


class TestBinarySTL:
    """Tests for the _mesh_to_binary_stl helper."""

    def test_stl_header(self) -> None:
        """Binary STL should have 80-byte header."""
        from backend.geometry.tessellate import _mesh_to_binary_stl

        mesh = MeshData(
            vertices=np.array(
                [[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32
            ),
            normals=np.array(
                [[0, 0, 1], [0, 0, 1], [0, 0, 1]], dtype=np.float32
            ),
            faces=np.array([[0, 1, 2]], dtype=np.uint32),
        )

        stl = _mesh_to_binary_stl(mesh)

        # Check header is 80 bytes
        assert len(stl) >= 84  # header + count
        assert stl[:5] == b"CHENG"

    def test_stl_triangle_count(self) -> None:
        """Binary STL triangle count should match face_count."""
        from backend.geometry.tessellate import _mesh_to_binary_stl

        mesh = MeshData(
            vertices=np.array(
                [[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32
            ),
            normals=np.array(
                [[0, 0, 1], [0, 0, 1], [0, 0, 1]], dtype=np.float32
            ),
            faces=np.array([[0, 1, 2]], dtype=np.uint32),
        )

        stl = _mesh_to_binary_stl(mesh)

        # Triangle count at offset 80
        count = struct.unpack_from("<I", stl, 80)[0]
        assert count == 1

    def test_stl_total_size(self) -> None:
        """Binary STL size = 80 + 4 + 50*N."""
        from backend.geometry.tessellate import _mesh_to_binary_stl

        mesh = MeshData(
            vertices=np.array(
                [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], dtype=np.float32
            ),
            normals=np.array(
                [[0, 0, 1]] * 4, dtype=np.float32
            ),
            faces=np.array([[0, 1, 2], [1, 3, 2]], dtype=np.uint32),
        )

        stl = _mesh_to_binary_stl(mesh)
        expected = 80 + 4 + 50 * 2
        assert len(stl) == expected


# ===================================================================
# Vertex normal computation tests
# ===================================================================


class TestVertexNormals:
    """Tests for _compute_vertex_normals helper."""

    def test_flat_triangle_normal(self) -> None:
        """A flat triangle in XY plane should have Z normals."""
        from backend.geometry.tessellate import _compute_vertex_normals

        vertices = np.array(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32
        )
        faces = np.array([[0, 1, 2]], dtype=np.uint32)

        normals = _compute_vertex_normals(vertices, faces)

        # All normals should point in +Z
        for i in range(3):
            assert abs(normals[i, 2]) > 0.99, f"Normal Z component: {normals[i, 2]}"

    def test_unit_length_normals(self) -> None:
        """Vertex normals should be unit length."""
        from backend.geometry.tessellate import _compute_vertex_normals

        vertices = np.array(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]],
            dtype=np.float32,
        )
        faces = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.uint32)

        normals = _compute_vertex_normals(vertices, faces)
        lengths = np.linalg.norm(normals, axis=1)

        np.testing.assert_array_almost_equal(lengths, np.ones(4))

    def test_empty_faces(self) -> None:
        """Empty face array should produce zero normals."""
        from backend.geometry.tessellate import _compute_vertex_normals

        vertices = np.array([[0, 0, 0], [1, 0, 0]], dtype=np.float32)
        faces = np.zeros((0, 3), dtype=np.uint32)

        normals = _compute_vertex_normals(vertices, faces)
        assert normals.shape == (2, 3)
        np.testing.assert_array_equal(normals, np.zeros((2, 3)))
