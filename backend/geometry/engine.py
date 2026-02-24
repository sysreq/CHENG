"""Geometry engine — CadQuery concurrency control and async entry points.

Track A provides only the CapacityLimiter singleton and derived-values
computation.  The actual geometry builders (assemble_aircraft, tessellate,
etc.) are implemented in Track B.
"""

from __future__ import annotations

import anyio

from backend.models import AircraftDesign, DerivedValues

# ---------------------------------------------------------------------------
# Module-level singleton — shared across REST, WebSocket, and export handlers.
# Limits concurrent CadQuery operations to 4 to keep peak memory under ~2 GB.
# ---------------------------------------------------------------------------
_cadquery_limiter = anyio.CapacityLimiter(4)


# ---------------------------------------------------------------------------
# Derived Values Computation (pure math — no CadQuery)
# ---------------------------------------------------------------------------


def compute_derived_values(design: AircraftDesign) -> DerivedValues:
    """Compute all 8 derived/read-only values from design parameters.

    Pure math — no CadQuery, no geometry.  Safe to call frequently.

    Formulas (from mvp_spec.md section 3.2 and implementation_guide.md section 2.5):
      1. wing_tip_chord_mm     = wing_chord * wing_tip_root_ratio
      2. wing_area_cm2         = 0.5 * (wing_chord + tip_chord) * wing_span / 100
      3. aspect_ratio          = wing_span^2 / wing_area_mm2
      4. mean_aero_chord_mm    = (2/3) * wing_chord * (1 + l + l^2) / (1 + l)
      5. taper_ratio           = tip_chord / wing_chord  (= wing_tip_root_ratio)
      6. estimated_cg_mm       = 0.25 * mean_aero_chord_mm
      7. min_feature_thickness  = 2 * nozzle_diameter
      8. wall_thickness_mm     = 1.6 (Conventional/Pod) or skin_thickness (BWB)
    """
    lambda_ = design.wing_tip_root_ratio

    wing_tip_chord_mm = design.wing_chord * lambda_
    wing_area_mm2 = 0.5 * (design.wing_chord + wing_tip_chord_mm) * design.wing_span
    wing_area_cm2 = wing_area_mm2 / 100.0
    aspect_ratio = (design.wing_span**2) / wing_area_mm2 if wing_area_mm2 > 0 else 0.0
    mean_aero_chord_mm = (
        (2.0 / 3.0) * design.wing_chord * (1 + lambda_ + lambda_**2) / (1 + lambda_)
        if (1 + lambda_) > 0
        else design.wing_chord
    )
    taper_ratio = wing_tip_chord_mm / design.wing_chord if design.wing_chord > 0 else 0.0
    estimated_cg_mm = 0.25 * mean_aero_chord_mm
    min_feature_thickness_mm = 2.0 * design.nozzle_diameter

    wall_thickness_map: dict[str, float] = {
        "Conventional": 1.6,
        "Pod": 1.6,
        "Blended-Wing-Body": design.wing_skin_thickness,
    }
    wall_thickness_mm = wall_thickness_map.get(design.fuselage_preset, 1.6)

    return DerivedValues(
        wing_tip_chord_mm=round(wing_tip_chord_mm, 2),
        wing_area_cm2=round(wing_area_cm2, 2),
        aspect_ratio=round(aspect_ratio, 2),
        mean_aero_chord_mm=round(mean_aero_chord_mm, 2),
        taper_ratio=round(taper_ratio, 4),
        estimated_cg_mm=round(estimated_cg_mm, 2),
        min_feature_thickness_mm=round(min_feature_thickness_mm, 2),
        wall_thickness_mm=round(wall_thickness_mm, 2),
    )
