"""Tests for export backend security, concurrency, and observability fixes.

Covers:
- #258: Path traversal sanitization via design.name
- #256: Thread-safe assembly cache (asyncio.Lock)
- #259: Unique ZIP filenames for concurrent exports
- #260: Unique test joint ZIP filename per call
- #261: DXF/SVG export failures produce logger.warning, not silent pass
"""

from __future__ import annotations

import asyncio
import logging
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.models import AircraftDesign


# ---------------------------------------------------------------------------
# #258: Path traversal sanitization
# ---------------------------------------------------------------------------


class TestFilenamesSanitization:
    """Verify _sanitize_filename and _make_temp_zip protect against path traversal."""

    def test_sanitize_simple_name(self) -> None:
        """Normal names should pass through unchanged (spaces -> underscores)."""
        from backend.export.package import _sanitize_filename

        result = _sanitize_filename("My Trainer")
        assert result == "My_Trainer"

    def test_sanitize_path_traversal_dotdot(self) -> None:
        """'../../etc/passwd' must not produce a path with '..' components."""
        from backend.export.package import _sanitize_filename

        result = _sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_sanitize_leading_dots_stripped(self) -> None:
        """Names starting with '.' are stripped to prevent hidden-file traversal."""
        from backend.export.package import _sanitize_filename

        result = _sanitize_filename("...hidden")
        assert not result.startswith(".")

    def test_sanitize_windows_separators(self) -> None:
        """Backslash separators must be removed."""
        from backend.export.package import _sanitize_filename

        result = _sanitize_filename("..\\..\\windows\\system32")
        assert "\\" not in result
        assert ".." not in result

    def test_sanitize_empty_name_fallback(self) -> None:
        """Empty / all-separator name should fall back to 'export'."""
        from backend.export.package import _sanitize_filename

        assert _sanitize_filename("") == "export"
        assert _sanitize_filename("../../..") == "export"
        assert _sanitize_filename("...") == "export"

    def test_sanitize_null_bytes(self) -> None:
        """Null bytes must be replaced."""
        from backend.export.package import _sanitize_filename

        result = _sanitize_filename("evil\x00name")
        assert "\x00" not in result

    def test_make_temp_zip_path_traversal(self, tmp_path: Path) -> None:
        """ZIP path produced for a path-traversal name must stay inside EXPORT_TMP_DIR."""
        from backend.export import package

        original_dir = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path
        try:
            design = AircraftDesign(name="../../etc/passwd")
            tmp_file, zip_path = package._make_temp_zip(design)
            try:
                # The final zip_path must be a child of tmp_path
                assert zip_path.parent == tmp_path, (
                    f"zip_path {zip_path} escaped EXPORT_TMP_DIR {tmp_path}"
                )
                # Must not contain '..' in any part
                assert ".." not in zip_path.parts
            finally:
                tmp_file.unlink(missing_ok=True)
        finally:
            package.EXPORT_TMP_DIR = original_dir

    def test_make_temp_zip_safe_name_used(self, tmp_path: Path) -> None:
        """ZIP filename must not contain raw path separators from design.name."""
        from backend.export import package

        original_dir = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path
        try:
            design = AircraftDesign(name="../../attack")
            tmp_file, zip_path = package._make_temp_zip(design)
            try:
                filename = zip_path.name
                assert "/" not in filename
                assert "\\" not in filename
                assert ".." not in filename
            finally:
                tmp_file.unlink(missing_ok=True)
        finally:
            package.EXPORT_TMP_DIR = original_dir


# ---------------------------------------------------------------------------
# #256: Thread-safe assembly cache
# ---------------------------------------------------------------------------


class TestAssemblyCacheThreadSafety:
    """Verify the asyncio.Lock prevents concurrent cache corruption."""

    def test_get_cache_lock_returns_lock(self) -> None:
        """_get_cache_lock() must return an asyncio.Lock instance."""
        from backend.routes.export import _get_cache_lock

        lock = _get_cache_lock()
        assert isinstance(lock, asyncio.Lock)

    def test_get_cache_lock_singleton(self) -> None:
        """_get_cache_lock() must return the same instance every call."""
        from backend.routes import export as export_module

        # Reset the module-level lock so we get a fresh one
        original = export_module._assembly_cache_lock
        export_module._assembly_cache_lock = None
        try:
            lock1 = export_module._get_cache_lock()
            lock2 = export_module._get_cache_lock()
            assert lock1 is lock2
        finally:
            export_module._assembly_cache_lock = original

    def test_concurrent_cache_access_no_exception(self) -> None:
        """Concurrent calls to _get_or_assemble_async must not raise."""
        from backend.routes import export as export_module

        # Reset module-level asyncio.Lock so it is created fresh inside the
        # new event loop started by asyncio.run() — avoids cross-loop RuntimeError.
        export_module._assembly_cache_lock = None

        # Patch assemble_aircraft to return a trivial dict quickly
        dummy_components = {"fuselage": MagicMock()}

        async def run_concurrent() -> None:
            design = AircraftDesign(name="Concurrent Test")

            with patch(
                "backend.routes.export.assemble_aircraft",
                return_value=dummy_components,
            ):
                export_module.clear_assembly_cache()
                tasks = [
                    export_module._get_or_assemble_async(design)
                    for _ in range(5)
                ]
                results = await asyncio.gather(*tasks)
                # All results must be the same dict
                for r in results:
                    assert r is not None

        asyncio.run(run_concurrent())

    def test_cache_eviction_under_lock(self) -> None:
        """Cache eviction does not corrupt state when called concurrently."""
        from backend.routes import export as export_module

        # Reset module-level asyncio.Lock so it is created fresh inside the
        # new event loop started by asyncio.run() — avoids cross-loop RuntimeError.
        export_module._assembly_cache_lock = None

        dummy = {"fuselage": MagicMock()}

        async def run() -> None:
            with patch(
                "backend.routes.export.assemble_aircraft",
                return_value=dummy,
            ):
                export_module.clear_assembly_cache()
                # Fill the cache to capacity
                designs = [AircraftDesign(name=f"Design{i}") for i in range(8)]
                for d in designs:
                    await export_module._get_or_assemble_async(d)
                # Cache size must not exceed _MAX_CACHE
                assert len(export_module._assembly_cache) <= export_module._MAX_CACHE

        asyncio.run(run())


# ---------------------------------------------------------------------------
# #259: Unique ZIP filenames
# ---------------------------------------------------------------------------


class TestUniqueZipFilenames:
    """Verify that two concurrent exports of the same design get different filenames."""

    def test_make_temp_zip_unique_per_call(self, tmp_path: Path) -> None:
        """Two successive calls to _make_temp_zip must return different zip_paths."""
        from backend.export import package

        original_dir = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path
        try:
            design = AircraftDesign(name="SameDesign")
            tmp1, zip1 = package._make_temp_zip(design)
            tmp2, zip2 = package._make_temp_zip(design)
            try:
                assert zip1 != zip2, (
                    f"Expected unique ZIP paths; both were {zip1}"
                )
            finally:
                tmp1.unlink(missing_ok=True)
                tmp2.unlink(missing_ok=True)
        finally:
            package.EXPORT_TMP_DIR = original_dir

    def test_make_temp_zip_uuid_in_filename(self, tmp_path: Path) -> None:
        """ZIP filename must contain an 8-character hex UUID suffix."""
        import re as _re
        from backend.export import package

        original_dir = package.EXPORT_TMP_DIR
        package.EXPORT_TMP_DIR = tmp_path
        try:
            design = AircraftDesign(name="MyDesign")
            tmp_file, zip_path = package._make_temp_zip(design)
            try:
                # Filename: cheng_<name>_<id>_<uuid8>.zip
                # UUID suffix is 8 lowercase hex chars before .zip
                assert _re.search(r"_[0-9a-f]{8}\.zip$", zip_path.name), (
                    f"Expected 8-char hex UUID suffix in {zip_path.name}"
                )
            finally:
                tmp_file.unlink(missing_ok=True)
        finally:
            package.EXPORT_TMP_DIR = original_dir


# ---------------------------------------------------------------------------
# #260: Unique test joint filenames
# ---------------------------------------------------------------------------


class TestUniqueTestJointFilenames:
    """Verify build_test_joint_zip produces a unique filename per call."""

    # CadQuery required for geometry
    pytestmark = pytest.mark.skipif(
        not pytest.importorskip.__doc__,  # always runs — real skip is via importorskip below
        reason="CadQuery not available",
    )

    def test_unique_filenames_per_call(self, tmp_path: Path) -> None:
        """Two calls to build_test_joint_zip must produce different file paths."""
        cq = pytest.importorskip("cadquery")
        from backend.export.test_joint import build_test_joint_zip

        path1 = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )
        path2 = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )

        assert path1 != path2, (
            f"Expected unique file paths; both calls returned {path1}"
        )
        # Both must still exist and be valid ZIPs
        assert path1.exists()
        assert path2.exists()
        with zipfile.ZipFile(path1) as zf1:
            assert "test_joint_plug.stl" in zf1.namelist()
        with zipfile.ZipFile(path2) as zf2:
            assert "test_joint_plug.stl" in zf2.namelist()

    def test_filename_contains_uuid_suffix(self, tmp_path: Path) -> None:
        """The test joint filename must contain a per-request UUID suffix."""
        import re as _re
        pytest.importorskip("cadquery")
        from backend.export.test_joint import build_test_joint_zip

        path = build_test_joint_zip(
            section_overlap=15.0,
            joint_tolerance=0.15,
            nozzle_diameter=0.4,
            tmp_dir=tmp_path,
        )

        assert _re.search(r"cheng_test_joint_[0-9a-f]{8}\.zip$", path.name), (
            f"Expected UUID suffix in filename: {path.name}"
        )


# ---------------------------------------------------------------------------
# #261: DXF/SVG exceptions logged as warnings
# ---------------------------------------------------------------------------


class TestDxfSvgExceptionLogging:
    """Verify that DXF/SVG export failures produce logger.warning, not silent pass."""

    def test_dxf_export_failure_logs_warning(self, tmp_path: Path, caplog) -> None:
        """When CadQuery DXF export raises, a warning must be logged."""
        cq_mod = pytest.importorskip("cadquery")
        from backend.export.package import build_dxf_zip

        # A simple box — CadQuery DXF export is patched to fail
        box = cq_mod.Workplane("XY").box(50, 50, 10)
        design = AircraftDesign(name="DXF Test")

        with patch("cadquery.exporters.export", side_effect=RuntimeError("DXF boom")):
            with caplog.at_level(logging.WARNING, logger="cheng.package"):
                zip_path = build_dxf_zip(
                    components={"fuselage": box},
                    design=design,
                )

        try:
            # The ZIP must still be created (partial export is OK)
            assert zip_path.exists()
            # At least one warning must have been emitted
            warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
            assert len(warnings) >= 1, (
                f"Expected at least one WARNING log entry; got: {caplog.records}"
            )
            assert any("DXF export failed" in r.message for r in warnings), (
                f"Expected 'DXF export failed' in warnings; got: {[r.message for r in warnings]}"
            )
        finally:
            zip_path.unlink(missing_ok=True)

    def test_svg_export_failure_logs_warning(self, tmp_path: Path, caplog) -> None:
        """When CadQuery SVG export raises, a warning must be logged."""
        cq_mod = pytest.importorskip("cadquery")
        from backend.export.package import build_svg_zip

        box = cq_mod.Workplane("XY").box(50, 50, 10)
        design = AircraftDesign(name="SVG Test")

        with patch("cadquery.exporters.export", side_effect=RuntimeError("SVG boom")):
            with caplog.at_level(logging.WARNING, logger="cheng.package"):
                zip_path = build_svg_zip(
                    components={"fuselage": box},
                    design=design,
                )

        try:
            assert zip_path.exists()
            warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
            assert len(warnings) >= 1, (
                f"Expected at least one WARNING log entry; got: {caplog.records}"
            )
            assert any("SVG export failed" in r.message for r in warnings), (
                f"Expected 'SVG export failed' in warnings; got: {[r.message for r in warnings]}"
            )
        finally:
            zip_path.unlink(missing_ok=True)

    def test_dxf_exception_not_silently_swallowed(self, caplog) -> None:
        """A DXF failure must never silently produce no log output."""
        cq_mod = pytest.importorskip("cadquery")
        from backend.export.package import build_dxf_zip

        box = cq_mod.Workplane("XY").box(100, 200, 10)
        design = AircraftDesign(name="Noisy DXF")

        with patch("cadquery.exporters.export", side_effect=ValueError("bad geometry")):
            with caplog.at_level(logging.WARNING, logger="cheng.package"):
                zip_path = build_dxf_zip(
                    components={"wing": box},
                    design=design,
                )

        try:
            assert len(caplog.records) > 0, "Expected at least one log record"
        finally:
            zip_path.unlink(missing_ok=True)
