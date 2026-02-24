# Cross-Review: UX Design & Product Requirements
## Reviewed from Aerospace Engineering Perspective

**Reviewer:** Aerospace Engineering Agent
**Date:** 2026-02-23
**Documents reviewed:**
- `X:\CHENG\docs\ux_design.md`
- `X:\CHENG\docs\product_requirements.md`
**Reference:** `X:\CHENG\docs\aero_parameters.md` (v1.1-draft)

---

## 1. Critical Aerodynamic Parameters Missing from UX Component Panels

### 1a. Wing Panel -- Missing from UX (present in aero spec)

- **Dihedral** (W07): Listed in UX doc as a wing panel parameter (good), but phased as 1.0 in my aero spec. Given that dihedral fundamentally affects stability and is visible in 3D, recommend promoting to **MVP** in both docs. A high-wing trainer with 0-deg dihedral looks wrong and flies wrong.
- **Wing position (High/Mid/Low)**: UX doc correctly places this in Global panel. No issue.

### 1b. Tail Panel -- No Issues

The UX tail panel (Type, Dihedral, Angle, Span, Chord, Incidence) maps exactly to T01, T14-T18 in the aero spec. No missing parameters.

### 1c. Fuselage Panel -- Deferred but OK

UX doc defers fuselage component editing to 1.0+. The aero spec has 8 MVP fuselage parameters (F01-F08, F12-F14). In practice, fuselage length and wing mount position are the most critical for MVP geometry generation. **Recommendation:** Even if the fuselage is not click-selectable in MVP, the fuselage length (F01) should be exposed somewhere -- either in the Global panel or as an editable dimension annotation. Currently neither doc exposes fuselage length as a user-editable field in MVP. The 300mm value from the mockup would be hardcoded or derived, which limits user control.

### 1d. Missing from Both Docs for MVP

- **Motor configuration (tractor/pusher)** (P02): The aero spec has this as MVP. Neither the UX doc nor the product doc expose it in the Global panel. A pusher vs tractor config completely changes the fuselage shape. **Recommend adding to Global panel** or deriving from fuselage preset.

**Verdict: Mostly aligned.** The UX panels cover the right parameters. The main gap is fuselage length not being user-editable in MVP.

---

## 2. Does MVP Include Enough for an Aerodynamically Plausible Plane?

**Yes, with caveats.**

The MVP parameter set across both docs covers:
- Wing planform: span, chord, taper ratio, sweep, incidence, airfoil -- **sufficient**
- Tail sizing: span, chord, dihedral, incidence -- **sufficient**
- Fuselage: type preset, length (implicit) -- **minimally sufficient**
- Tail type selection: conventional, T-tail, V-tail -- **sufficient**

**Caveats:**

1. **No tail arm control in MVP.** The distance from wing to tail (T22, `tailArm`) is arguably the single most important stability parameter after wing area and tail area. If this is purely derived from fuselage length and wing mount position (which are not directly editable in the UX MVP), the user has no way to influence longitudinal stability. The system will generate whatever tail arm results from the fuselage preset. This is acceptable IF the presets produce reasonable tail arms (2.5--3x MAC), but should be explicitly validated in the code.

2. **No wing loading feedback in MVP.** Both docs defer computed values (wing area, aspect ratio, wing loading) to 1.0. However, the aero spec marks D01-D04 as MVP-derived. **Recommend the UX doc display at least wing area and aspect ratio as read-only computed values in MVP.** These are trivial to calculate and immediately tell an experienced user whether the plane is plausible.

3. **Dihedral at 0-deg default with no MVP control** could produce a mid-wing or low-wing plane that is laterally unstable. Most beginners will never notice until they build it. Promote dihedral to MVP or ensure the presets include appropriate dihedral per wing position.

**Verdict: MVP is aerodynamically viable** for generating a plausible shape. The combination of presets + basic wing/tail parameters produces something that looks right. True aerodynamic validation (will it actually fly?) is appropriately deferred to 1.0.

---

## 3. Export Format Issue: DXF/SVG vs STL

**FLAGGED: The UX doc has been updated and is now correct.** The UX doc (v1.1) correctly shows:

- STL as **MVP** export (Section 7.1 table, row 1)
- DXF as **1.0** (not MVP)
- SVG as **1.0** (not MVP)

The product requirements doc is also correct:
- E-01 (STL export): Must priority
- E-06 (DXF/SVG): Could priority
- Phase 1 MVP table: "STL export (primary format)" listed
- MVP Excluded list: "PDF/DXF/SVG export" correctly excluded

**However, one minor inconsistency in the UX doc:** The export dialog mockup (Section 7.3) shows `[STL (primary)] [STEP] [DXF]` as toggle buttons. Since STEP and DXF are both 1.0 features, the MVP export dialog should only show STL. The dialog mockup appears to be drawn for the 1.0 version, not MVP. **Recommendation:** Add a note clarifying that the MVP export dialog is simplified (STL only, no format toggle), and the multi-format dialog is the 1.0 version.

**Verdict: No blocking issue.** Both docs correctly prioritize STL for MVP. The export dialog mockup just needs a clarifying note about MVP vs 1.0 scope.

---

## 4. Parameter Grouping Issues (Global vs Component)

### 4a. Wing Position in Global Panel -- Correct

UX doc places Wing Position (High/Mid/Low/Shoulder) in the Global panel. This is correct -- it fundamentally changes the aircraft character and stability behavior. Agree with UX doc's rationale in Section 10.

### 4b. Chord in Global Panel -- Correct but Needs Clarification

UX doc shows "Chord" in Global panel. Product doc says "chord input." The aero spec has `wingChord` (G05) as the root chord in Global, with `wingTipChord` (W03) and `wingTipRootRatio` (W04) as component-level.

The UX doc's Global panel table says "Chord: Two text inputs -- Root chord and tip chord." This is slightly different from the mockup, which shows a single CHORD field. **Recommendation:** Keep the mockup's single CHORD field as root chord in Global. Tip chord is derived via Tip/Root Ratio in the wing component panel. Two chord fields in Global is redundant with the component panel and adds clutter.

### 4c. Tail Span in Global -- Questionable

The aero spec puts `tailSpan` (G04) in Global (matching the mockup's second SPAN field). The UX doc does NOT list tail span in the Global panel -- it only appears in the Tail component panel. **This is actually better UX.** The mockup shows two SPAN fields which is confusing. Having wing span in Global and tail span only in the Tail component panel is cleaner. **Recommendation:** Deviate from the mockup. Remove the second SPAN field from Global. Tail span belongs in the component panel. Update the aero spec accordingly.

### 4d. Engines in Global -- Correct but Incomplete

Both docs list engine count in Global. The aero spec also has `motorConfig` (tractor/pusher) as MVP. Neither UX nor product doc expose tractor/pusher in the Global panel. **Recommendation:** Add a small dropdown or toggle next to the engine count: "Nose" / "Rear" (user-friendly labels for tractor/pusher). This matches the mockup which shows "ENGINES: [ ] [ ]" -- two fields suggesting count + position.

**Verdict: Generally well-grouped.** The main fix is removing tail span from Global and adding motor position next to engine count.

---

## 5. Missing 3D Printing Parameters

Both docs have been updated for 3D printing and are substantially aligned with the aero spec's Section 9 (PR01-PR24). Checking for gaps:

### 5a. Covered in Both Docs (Good)

- Print bed size (X, Y, Z) -- covered
- Auto-sectioning -- covered
- Wall thickness -- covered
- Alignment joints/connectors -- covered
- Per-part STL export -- covered
- Trailing edge thickening -- covered (UX: "trailing edge too sharp" warning; aero spec: PR09)

### 5b. In Aero Spec but Not in UX/Product Docs

| Parameter | Aero Spec ID | Gap |
|-----------|-------------|-----|
| **Nozzle diameter** (PR06) | MVP | Neither doc mentions this. It drives minimum feature thickness and wall thickness validation. **Recommend adding to the export dialog or a global print settings panel.** |
| **Joint tolerance** (PR11) | MVP | Neither doc mentions this. Critical for usable prints -- every printer is different. **Recommend adding to export dialog.** |
| **Joint type selection** (PR10) | MVP | Neither doc exposes tongue-and-groove vs dowel-pin vs flat-with-pins as a user choice. The UX doc just says "alignment features." **Recommend adding to export dialog as an advanced option.** |
| **STL tolerance** (PR21) | MVP | Neither doc exposes tessellation quality. For most users the default is fine, but power users want control. **Recommend as an advanced option in the export dialog.** |
| **Spar channel toggle** (PR15) | 1.0 | Product doc mentions spar channels (E-05) as "Should." UX doc does not detail the UI for this. Covered in 1.0 scope. |
| **Servo pocket dimensions** (PR17-19) | 1.0 | Neither doc specifies servo pocket UI. This is fine for 1.0 deferral. |

### 5c. In UX/Product Docs but Not in Aero Spec

| Item | Source | Gap |
|------|--------|-----|
| **Infill percentage recommendation** | Product doc (E-05), UX (Section 7.2) | The aero spec does not include an infill parameter because infill is a slicer concern, not a geometry concern. However, the parts manifest could include recommended infill per part. Not a geometry parameter -- belongs in the export metadata, not the parameter spec. No action needed on aero spec. |
| **Print orientation suggestion** | Product doc (E-10), UX (Section 7.2) | Aero spec's wing/fuselage sections include print orientation notes, but there is no formal parameter for it. This is correct -- orientation is a per-part export metadata item, not a configurable parameter. No action needed. |

### 5d. Net New Recommendations for 3D Printing

1. **Test joint export:** The aero spec (Section 9.6) suggests a "print test joint" button. Neither the UX nor product doc includes this. **Strongly recommend for MVP.** Users waste hours and filament if joints don't fit. A one-click "print a test joint piece" that exports a small 20x20x10mm block with the configured joint tolerance would save enormous frustration.

2. **Wing spar alignment across sections:** When a wing is sectioned into 3 pieces, the spar channel must align across all joints. Both docs mention spar channels but neither explicitly states that spar holes must be co-axial across section boundaries. The aero spec covers this (Section 4.7) but the product acceptance criteria should include it: "spar channel in section N aligns with spar channel in section N+1 to within 0.2mm."

**Verdict: Good coverage.** The main gaps are nozzle diameter, joint tolerance, and joint type not being in the UX export dialog. These are practical print parameters that significantly affect usability. The test joint feature is a high-value, low-effort addition.

---

## Summary of Key Findings

| # | Finding | Severity | Recommendation |
|---|---------|----------|---------------|
| 1 | Fuselage length not user-editable in MVP | Medium | Expose in Global panel or as editable dimension annotation |
| 2 | Motor config (tractor/pusher) not in Global panel | Medium | Add dropdown next to engine count |
| 3 | Tail span should not be in Global panel | Low | Remove from Global, keep in Tail component panel only |
| 4 | Wing dihedral should be MVP, not 1.0 | Low | Promote to MVP or ensure presets set appropriate values |
| 5 | Computed values (wing area, AR) should display in MVP | Low | Add read-only display under wing parameters |
| 6 | Export dialog mockup shows 1.0 format options | Low | Add note clarifying MVP dialog is STL-only |
| 7 | Nozzle diameter missing from UX export settings | Medium | Add to export dialog or global print settings |
| 8 | Joint tolerance missing from UX export settings | Medium | Add to export dialog |
| 9 | Test joint export feature missing | Medium | Add "Print Test Joint" button to export dialog |
| 10 | Spar alignment across sections not in acceptance criteria | Low | Add to product doc Section 7.4 |
| 11 | Root chord vs "two chord inputs" inconsistency | Low | Keep single root chord in Global, tip via Tip/Root Ratio |

**Overall assessment:** Both documents are well-written and substantially aligned with the aero parameter spec. The UX doc correctly prioritizes STL for MVP and handles the 3D printing workflow well. The product doc's user stories cover the right scope. The gaps identified above are refinements, not fundamental issues. No blocking problems found.
