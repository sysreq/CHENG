# Cross-Review: Aerospace Parameters from Product Perspective

**Reviewer:** Product Manager
**Document reviewed:** `X:\CHENG\docs\aero_parameters.md` (v1.1-draft, by Aerospace Engineering Agent)
**Date:** 2026-02-23

---

## 1. Are the 49 MVP Parameters Actually Minimal Enough?

**Assessment: The count is higher than ideal but mostly justified. I recommend cutting 5--8 parameters to bring the MVP closer to 40.**

The aero doc lists 49 MVP parameters (Appendix B). For a tool whose MVP tagline is "First Printable Plane," 49 user-facing parameters is a lot --- especially for the Beginner Builder persona (Alex) who should be able to go from preset to export in under 10 minutes. Every additional parameter is a decision point that slows the user down.

### Parameters I recommend cutting from MVP (defer to 1.0)

| Parameter | ID | Reason to defer |
|---|---|---|
| `wingSections` | W08 | MVP should generate a single straight panel per half-wing. Multi-panel/polyhedral adds UI complexity (the panel-break sub-parameters W09--W11 are already 1.0, so having `wingSections` in MVP with no way to configure the extra panels is confusing). Default to 1, hide the field. |
| `wingIncidence` | W06 | The aero doc defaults it to 2 degrees, which is correct for most trainer/sport planes. Beginners won't know what incidence is. A 2-degree default baked in is fine for MVP. Expose it in 1.0. |
| `vTailAngle` | T15 | This is derived from `vTailDihedral` (T14) via `angle = 180 - 2 * dihedral`. Showing both in MVP is redundant and confusing. Keep T14 (dihedral) and auto-derive T15. Show T15 as a read-only display in 1.0. |
| `noseShape` | F05 | MVP fuselage can use a single sensible nose shape per fuselage preset. Exposing 5 nose shape options (Pointed, Rounded, Flat, Ogive, Elliptical) adds choice paralysis for beginners. Defer to 1.0; in MVP the fuselage preset determines the nose. |
| `noseLength` | F06 | Same reasoning as F05. Let the fuselage preset control nose proportions in MVP. |
| `tailTaper` | F07 | Fuselage tail taper is a nuanced shape detail. The fuselage preset should handle this in MVP. |
| `stlTolerance` | PR21 | The default of 0.01 works for essentially all RC plane use cases. Exposing tessellation tolerance to beginners is unnecessary. Hardcode the default in MVP; expose in 1.0 for power users. |

**Cutting these 7 brings the MVP to 42 parameters** --- still substantial but more focused. Importantly, none of these cuts reduce the geometric capability of the MVP; they just hide parameters that have sensible defaults or are derived from others.

### Parameters that should stay MVP despite temptation to cut

| Parameter | ID | Why it must stay |
|---|---|---|
| `wallThickness` (fuselage) | F14 | Directly affects whether the STL is printable. Must stay. |
| `wingSkinThickness` | W20 | Same reasoning. Must stay. |
| `printBedX/Y/Z` | PR01--03 | Users with different printers must be able to configure this. Critical for correct auto-sectioning. |
| `jointType` | PR10 | Different users prefer different joint methods. Even MVP needs this choice. |
| `jointTolerance` | PR11 | Every FDM printer is different. A user whose parts don't fit because the tolerance is wrong will abandon the tool. |

---

## 2. Parameters That Should Be Promoted to MVP

**Assessment: The aero engineer got most of the promotions right. I recommend one additional promotion.**

| Parameter | ID | Current Phase | Recommend | Reasoning |
|---|---|---|---|---|
| `motorConfig` (Tractor/Pusher) | P02 | MVP | Correct | Good call having this in MVP. A pusher vs tractor config fundamentally changes the aircraft shape. |
| `wallThickness` | F14 | MVP | Correct | Essential for 3D printing. |
| `wingSkinThickness` | W20 | MVP | Correct | Essential for 3D printing. |
| `wingDihedral` | W07 | 1.0 | **Promote to MVP** | Dihedral is a highly visible geometric feature (you can see it immediately in 3D). A trainer with 3 degrees of dihedral looks very different from a flat wing. It's a simple single-angle input that beginners can understand ("wings tilted up = more stable"). The aero doc defaults it to 3 degrees, which is fine, but hiding it means users can't flatten the wing for an aerobatic look or increase it for a trainer. It's a one-parameter change with high visual and aerodynamic impact. |

I considered promoting `wingWashout` (W16) but decided against it. Washout is aerodynamically important but visually subtle and hard for beginners to understand. Keeping it at 1.0 is correct.

---

## 3. Does the Parameter Phasing Align with the Product Phasing Strategy?

**Assessment: Strong alignment overall, with a few discrepancies to resolve.**

### Well-aligned areas

- **MVP scope matches.** The aero doc's MVP (basic fuselage + wing + tail + 3D printing params + STL export) maps directly to the PRD Phase 1 "First Printable Plane."
- **Control surfaces at 1.0.** Both docs agree that control surfaces are auto-generated in MVP and become configurable in 1.0. The aero doc's decision key D5 explicitly states this.
- **Landing gear at 1.0.** Both docs agree.
- **Validation as warnings, not blocks.** Both docs agree (aero doc D6, PRD Section 7.6).

### Discrepancies to resolve

| Area | Aero Doc | PRD | Resolution needed |
|---|---|---|---|
| **Presets in MVP** | The aero doc lists 7 presets (Section 11.1) but marks the aircraft preset dropdown (G08) as **1.0**, not MVP. The presets themselves have a section header "MVP Presets (Phase: 1.0)" which is contradictory. | PRD requires 3 presets in MVP. | **The aero doc should mark G08 as MVP** and rename Section 11.1 to "Presets (Phase: MVP)." Without presets, the MVP is unusable for beginners. Start with 3 presets (Trainer, Sport, Aerobatic) in MVP and add the remaining 4 in 1.0. |
| **Derived parameters in MVP** | The aero doc shows 4 derived params in MVP (wing area, AR, MAC, taper ratio). | PRD says computed aerodynamic values are excluded from MVP. | **Align on the aero doc's approach.** These 4 values are trivially cheap to compute and provide immediate value. Displaying them in the UI as read-only info does not add complexity for the user. The PRD should be updated to allow these 4 basic derived values in MVP. |
| **DXF/SVG export** | Not mentioned in aero doc (correctly, since it's a 3D-printing-focused tool). | PRD lists DXF/SVG as "Could Have" for 1.0. | Aligned --- both treat it as secondary. No action needed. |
| **Number of MVP presets** | Aero doc defines 7 presets. | PRD requires 3 for MVP, 10+ for 1.0. | Start with 3 in MVP: **Trainer, Sport, Aerobatic.** Add Glider, Delta/Flying Wing, Scale, Micro Foamie in 1.0. The aero doc's 7 presets are all well-defined and useful; the question is just how many to ship on day one. |

---

## 4. Are the Default Values Beginner-Friendly?

**Assessment: Mostly yes, with two concerns.**

### Defaults that work well for beginners

- **Wingspan 1000mm** --- good mid-range sport size. Prints in manageable sections.
- **Clark-Y airfoil** --- classic flat-bottom trainer foil. Easy to understand, forgiving stall behavior.
- **Conventional tail** --- the most intuitive tail type for beginners.
- **High-Wing mount** --- most stable configuration, correct for a trainer.
- **Wall thickness 1.6mm** (fuselage) and **1.2mm** (wing) --- strong enough for PLA, not wastefully heavy.
- **Print bed 220x220mm** --- matches the most popular printer class (Prusa, Ender 3, Bambu A1).
- **Tongue-and-groove joints** --- self-aligning, easiest to glue.
- **Joint tolerance 0.15mm** --- reasonable starting point for most printers.

### Defaults I would change

| Parameter | Current default | Recommended | Reasoning |
|---|---|---|---|
| `fuselagePreset` (G01) | `Conventional` | Keep as-is | Correct for beginners. |
| `wingIncidence` (W06) | 2 degrees | Keep, but **hide in MVP** (see Section 1 above) | 2 degrees is correct for a trainer. No need to expose it. |
| `tailTaper` (F07) | 0.15 | Keep, but **hide in MVP** | 0.15 is fine. Beginners don't need to think about this. |
| `wingSweep` (W05) | 0 degrees | Keep as-is | Zero sweep is correct for a trainer/sport plane. The mockup shows 25 degrees sweep, but that's a demo view, not the recommended default. |
| `vTailDihedral` (T14) | 35 degrees | Keep as-is | Only visible when V-tail is selected. 35 degrees is the standard V-tail angle. |
| `engineCount` (G02) | 1 | Keep as-is | Single engine is the norm. |
| `wingTipRootRatio` (W04) | 0.67 | **Change to 1.0** for MVP default | A rectangular wing (ratio 1.0) is simpler to understand and build. Taper adds aerodynamic efficiency but also complexity. For a beginner's first design, a rectangular wing is more forgiving (uniform chord means uniform lift distribution, no tip-stall tendency). Change the default to 1.0 in MVP; presets like "Sport" or "Glider" can set it to 0.67 or lower. |
| `exportPerPart` (PR23) | `on` | Keep as-is | Per-part STL is essential. Correct default. |

---

## 5. Should 3D-Printing-Specific Parameters Come Earlier?

**Assessment: The aero engineer already promoted the critical ones. A few more adjustments needed.**

The aero doc has done an excellent job of creating a dedicated Section 9 (3D Printing / Fabrication Parameters) with 10 MVP parameters. This is well-aligned with the PRD's emphasis on 3D printing as primary fabrication.

### Already correctly in MVP

- Print bed dimensions (PR01--03) --- essential
- Auto-sectioning toggle (PR04) --- essential
- Joint overlap (PR05) --- essential
- Nozzle diameter (PR06) --- essential (drives minimum feature calculations)
- Min feature thickness (PR08) --- essential (derived from nozzle)
- Trailing edge min thickness (PR09) --- essential (prevents unprintable sharp edges)
- Joint type (PR10) --- important for user preference
- Joint tolerance (PR11) --- critical for fitment
- Hollow parts toggle (PR14) --- essential (solid wings would be absurdly heavy)
- Export format (PR20) --- essential
- Export per part (PR23) --- essential

### Recommendations for additional 3D printing considerations

| Consideration | Current state | Recommendation |
|---|---|---|
| **Print orientation guidance** | Not a parameter; noted in text (Section 4.7). | Add a **read-only derived field** in MVP that shows recommended print orientation per part (e.g., "Fuselage: on side, Wing: trailing edge down"). This is not a user-configurable parameter but a computed recommendation displayed in the export panel. Include in PRD acceptance criteria. |
| **Part count estimate** | Not exposed. | Add a **read-only derived field** showing total number of printed parts after sectioning (e.g., "This design produces 9 printable parts"). Helps users gauge the scope of the print job before committing. Trivial to compute. |
| **Estimated print weight** | D11, marked Future. | Keep at Future. Requires material density and volume computation. Not critical for MVP. |
| **Spar channels** | PR15, marked 1.0. | Keep at 1.0. In MVP, the wing is a hollow shell. Users can insert spars through the spar channel feature in 1.0. For MVP, the wing joint overlap (tongue-and-groove) provides adequate structural connection between sections. |

---

## 6. Overall Assessment

The aerospace parameter document is thorough, well-structured, and well-aligned with the product requirements. The CadQuery implementation notes per section are particularly valuable --- they bridge the gap between "what parameter does the user see" and "how does the backend generate it."

### Summary of recommended changes

| # | Change | Impact |
|---|---|---|
| 1 | Cut 7 parameters from MVP (W08, W06, T15, F05, F06, F07, PR21) | Reduces MVP from 49 to 42 params. Simpler onboarding. |
| 2 | Promote `wingDihedral` (W07) to MVP | Adds 1 param back, net 43. High visual impact for low complexity. |
| 3 | Mark aircraft presets (G08) as MVP, not 1.0 | Presets are essential for beginners. Ship 3 in MVP. |
| 4 | Change default `wingTipRootRatio` to 1.0 | Rectangular wing is more beginner-friendly. Presets override. |
| 5 | Align PRD to allow 4 basic derived values in MVP | Wing area, AR, MAC, taper ratio. Cheap to compute, valuable feedback. |
| 6 | Add read-only "part count estimate" to MVP export panel | Helps users gauge print job scope. |
| 7 | Add read-only "print orientation recommendation" to MVP export | Helps users orient parts correctly in slicer. |

**Net MVP parameter count after changes: ~43 user-configurable + 6 derived/read-only = 49 displayed values.** This is coincidentally the same number as the aero doc's original count, but the composition is better: fewer obscure shape parameters, more actionable print guidance.

---

## 7. Cross-Reference: PRD Updates Needed

Based on this review, the following PRD sections need minor updates:

1. **Section 5, Phase 1 MVP:** Add "4 basic derived values displayed (wing area, aspect ratio, MAC, taper ratio)" to the Included table. Remove these from the "Excluded from MVP" list.
2. **Section 5, Phase 1 MVP:** Add "3 built-in presets selectable from dropdown" (already listed, but confirm alignment with aero doc's preset definitions for Trainer, Sport, Aerobatic).
3. **Section 7.4 (STL Export acceptance criteria):** Add criterion: "Export panel displays total part count and per-part print orientation recommendation."
4. **Section 6 (MoSCoW):** Move "Built-in presets (minimum 3)" from Must Have to confirm it includes a preset *selector dropdown* in the global panel, not just hardcoded defaults.

These are minor adjustments. The two documents are fundamentally well-aligned.
