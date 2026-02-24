# Cross-Review: Aerospace Parameters from UX Perspective

> **Reviewer:** UX Expert
> **Document Reviewed:** `X:\CHENG\docs\aero_parameters.md` (v1.1-draft)
> **Date:** 2026-02-23

---

## 1. Are 37 MVP Parameters Manageable?

**Verdict: Yes, but only because of the panel architecture.** The user never sees 37 parameters at once. Here is how they distribute across the UI:

| Panel | MVP Parameters | Count |
|-------|---------------|-------|
| Global Parameters (right, always visible) | G01-G06 (Fuselage preset, Engines, Wing Span, Tail Span, Wing Chord, Tail Type) | 6 |
| Fuselage Component (bottom-left, on click) | F01-F07, F12-F14 (Length, Width, Height, Nose Shape, Nose Length, Tail Taper, Wing Mount Position, Wing Mount Type, Wall Thickness) | 9 |
| Wing Component (bottom-left, on click) | W01-W06, W08, W12, W20 (Span*, Root Chord*, Tip Chord, Tip/Root Ratio, Sweep, Incidence, Sections, Airfoil, Skin Thickness) | 9 |
| Tail Component (bottom-left, on click) | T01*, T02/T14, T03/T17, T06/T18, T09, T10, T16, T22 (Type*, H-Stab or V-Tail params depending on type, Tail Arm) | 7-8 |
| 3D Print Settings (export dialog) | PR01-PR06, PR09-PR11, PR14, PR20-PR21, PR23 (Bed size, Auto-section, Overlap, Nozzle dia, TE thickness, Joint type, Joint tolerance, Hollow, Export format, STL tolerance, Per-part) | 12 |

*Parameters marked with * are mirrored from Global (shown in both places, same value).*

**Maximum visible at once: ~15** (6 global + up to 9 component). This is comfortable -- well within the 7-plus-or-minus-2 cognitive load guideline per logical group, since each panel has clear groupings.

**Recommendations:**

- **Group the fuselage panel into two visual sections:** "Shape" (F01-F07) and "Layout" (F12-F14). A thin separator line between them is enough.
- **Group the wing panel into two sections:** "Planform" (Span, Chord, Tip/Root, Sweep, Sections) and "Profile" (Airfoil, Incidence, Skin Thickness).
- **Move 3D print parameters (PR01-PR23) out of the component panels entirely for MVP.** They belong in the Export dialog or a dedicated "Print Settings" section accessible from the toolbar. Mixing aerodynamic parameters with print parameters in the same panel creates cognitive friction -- the user is thinking about the shape of their plane, not about nozzle diameters. Exception: Wall Thickness (F14, W20) can stay in the component panels because it directly affects the visual geometry.
- **Nozzle Diameter (PR06) should be a one-time preference, not a per-session parameter.** Set it once in Settings, persist it between sessions. Most users have one printer and never change their nozzle.

---

## 2. Parameters Needing Special UI Treatment

### 2a. Bidirectional Linked Parameters

The aero doc identifies two bidirectional pairs:

**Tip Chord (W03) <--> Tip/Root Ratio (W04):**
- Editing Tip/Root Ratio recalculates Tip Chord. Editing Tip Chord recalculates Tip/Root Ratio.
- **UI treatment:** Show both fields in the wing panel. The most recently edited field is the "primary" (normal style). The other is displayed as "derived" (italic text, small "auto" tag). When the user edits the derived field, it becomes primary and the other switches to derived. This prevents confusion about which value "wins."
- The mockup shows Tip/Root Ratio as the visible control. I recommend making it the default primary, with Tip Chord shown as a secondary derived value below it.

**V-Tail Dihedral (T14) <--> V-Tail Angle (T15):**
- Same bidirectional relationship: `Angle = 180 - 2 * Dihedral`.
- **UI treatment:** Same primary/derived pattern. Dihedral is the more intuitive control for RC builders (they think "how angled is my V-tail"), so make it the default primary. Angle is the derived value shown below. But both are editable.

**Implementation note:** The frontend should handle bidirectional updates locally (no round-trip to CadQuery needed). Only send the canonical value to the backend.

### 2b. Parameters with Conditional Visibility

Several parameters only make sense in certain configurations (see Section 3 below). The aero doc calls these out clearly in Section 13.1. These need animated show/hide transitions.

### 2c. Computed Read-Only Values (D01-D04 in MVP)

Wing Area (D01), Aspect Ratio (D02), MAC (D03), and Taper Ratio (D04) are derived and read-only.

- **UI treatment:** Display in a "Computed Values" row at the bottom of the wing component panel, visually distinct from editable parameters. Use a lighter font color, no input border, and a small calculator icon. These values update live as the user changes planform parameters.
- **Format:** Wing Area should be shown in cm^2 (not mm^2) for readability. "Wing Area: 1800 cm^2" is more meaningful than "1,800,000 mm^2".

### 2d. Wall Thickness and Nozzle Diameter Coupling

The aero doc notes that wall thickness should be a multiple of nozzle diameter (V17). The UI should enforce this with a smart stepper: instead of free text input, Wall Thickness should use a stepper that increments in multiples of Nozzle Diameter (e.g., 0.8, 1.2, 1.6, 2.0 for a 0.4mm nozzle). This eliminates invalid values entirely.

### 2e. Tail Type (T01/G06) -- Mirrored Parameter

This parameter appears in both the Global panel and the Tail component panel. Both instances must stay in sync. Changing it in either location should:
1. Update the other location immediately.
2. Trigger the visibility dependency cascade (see Section 3).
3. Reset tail sub-parameters to defaults for the new type (with a toast notification).

---

## 3. Show/Hide Transition Design for Visibility Dependencies

The aero doc's Section 13.1 defines a comprehensive dependency graph. Here is how each transition should work in the UI:

### 3a. Tail Type Changes (Most Complex)

When the user changes Tail Type in the Global panel (or in the Tail component panel):

**Transition from Conventional to V-Tail:**
1. If the tail component panel is currently open, its contents animate:
   - H-Stab fields (T02-T08) fade out over 150ms.
   - V-Stab fields (T09-T13) fade out over 150ms.
   - V-Tail fields (T14-T21) fade in over 150ms, staggered 30ms per field (top to bottom).
2. The 3D viewport shows CadQuery regenerating the tail geometry (loading spinner if > 300ms).
3. A toast notification appears: "Switched to V-Tail. Tail parameters reset to defaults."
4. If the tail is NOT currently selected, the transition happens silently. The next time the user clicks the tail, the correct fields appear.

**Transition from any type to Flying-Wing:**
1. The entire tail component disappears. If the tail was selected, the component panel reverts to "SELECT A COMPONENT TO CONFIGURE."
2. The tail mesh is removed from the Three.js scene.
3. Clicking the wing now shows additional elevon parameters (C21-C24) in a "Control Surfaces" sub-section (1.0 feature).
4. Toast: "Flying wing -- tail removed. Control via elevons."

**General principle:** Never show blank/disabled fields for an irrelevant configuration. Hide them entirely. Disabled grayed-out fields create visual noise and imply "this exists but you can't use it," which is confusing when the feature genuinely does not apply.

### 3b. Fuselage Type Changes

When switching from Conventional to Pod-and-Boom:
- Boom Diameter (F10) and Boom Length (F11) fields animate in below the existing fuselage fields.
- A thin separator line and "BOOM" sub-header appear above them.

When switching back:
- The boom fields fade out and the separator/header disappears.

### 3c. Wing Sections Changes

When the user increases Sections (W08) from 1 to 2:
- A new "PANEL 2" sub-section appears in the wing component panel with Panel Break Position (W09) and Panel Dihedral (W10) fields.
- Each additional section adds another sub-section.
- Reducing sections removes the bottom-most panel sub-section with a fade-out.

### 3d. Animation Specifications

| Transition | Duration | Easing | Style |
|-----------|----------|--------|-------|
| Field appear | 150ms | ease-out | Fade in + slide down 8px |
| Field disappear | 120ms | ease-in | Fade out + slide up 4px |
| Group appear (multiple fields) | 150ms + 30ms stagger per field | ease-out | Cascading fade-in |
| Panel content swap (full component change) | 200ms | ease-in-out | Cross-fade |

These are fast enough to feel responsive but slow enough to be perceivable, so the user understands that the UI changed rather than feeling like fields teleported.

---

## 4. Export Phasing Update (STL as MVP)

**Already addressed.** I updated the UX design document (`ux_design.md`) earlier in this session to make STL the primary MVP export format. The current state of the UX doc reflects:

- **MVP:** STL export (via CadQuery backend) with auto-sectioning for print bed size, alignment connectors, and a parts manifest. ZIP download containing all STL files.
- **1.0:** STEP and DXF added as secondary formats.
- **Future:** PDF build plans, slicer integration.

The export dialog in the UX doc is already redesigned around 3D printing (printer bed size inputs, auto-section toggle, wall thickness, connector options).

**One additional recommendation from this review:** The aero doc introduces PR20 (`exportFormat`) and PR24 (`stepExport`) as separate parameters. From a UX perspective, these should be a single multi-select in the Export dialog (checkboxes for STL, STEP, DXF) rather than separate toggle parameters. The export dialog is the right place for format selection -- it should not live in a parameter panel.

---

## 5. Parameter Naming / Beginner-Friendliness

Several parameters use terminology that may confuse hobby-level users. Recommendations:

| Parameter | Current Label | Suggested Label | Reason |
|-----------|-------------|-----------------|--------|
| W06 `wingIncidence` | Incidence | Wing Angle | "Incidence" is aerospace jargon. "Angle" with a tooltip "Angle of the wing relative to the fuselage (positive = nose up)" is clearer. The mockup uses "INCIDENT" which is even more confusing. |
| T14 `vTailDihedral` | Dihedral | V-Tail Tilt | "Dihedral" is jargon. "Tilt" with a tooltip "How far the V-tail surfaces are tilted from horizontal" is more intuitive. |
| T15 `vTailAngle` | Angle | V-Tail Spread | "Angle" is ambiguous (angle of what?). "Spread" communicates "how wide apart are the two V-tail surfaces." |
| W04 `wingTipRootRatio` | Tip/Root Ratio | Taper | The mockup says "TIP/ROOT RATIO" which is fine for the label, but the concept is "taper." Consider: "Taper (Tip/Root)" as the label. |
| T22 `tailArm` | Tail Arm | Tail Distance | "Arm" is a torque/moment term from aerospace. "Distance" (with tooltip "Distance from wing to tail") is immediately clear. |
| W08 `wingSections` | Sections | Wing Panels | "Sections" could mean cross-sections. "Panels" is what RC builders actually call the spanwise segments of a polyhedral wing. |
| F12 `wingMountPosition` | Wing Mount Position | Wing Placement | "Mount Position" sounds like a bolt pattern. "Placement" with a percentage slider is more natural. |
| W16 `wingWashout` | Washout (Twist) | Tip Twist | "Washout" is jargon. Most beginners have no idea what it means. "Tip Twist" with tooltip "Twist the wing tip downward to prevent tip stalls" is self-explanatory. |
| D02 `aspectRatio` | Aspect Ratio | Wing Slenderness (AR) | "Aspect Ratio" is moderately well-known but adding a plain-English alternative helps. Or just keep "Aspect Ratio" but add a tooltip: "How long and narrow the wing is. Higher = more efficient glide, lower = more agile." |
| D03 `meanAeroChord` | MAC | Avg. Wing Width (MAC) | "Mean Aerodynamic Chord" means nothing to a beginner. "Average Wing Width" is the plain-English equivalent. Keep "MAC" in parentheses for users who know the term. |

**General guideline:** Every parameter should have a tooltip (shown on hover or via an info icon) that explains what it does in one sentence without jargon. The aero doc's "Description" column is a good starting point but needs simplification. Example:

- Aero doc: "Wing root incidence angle relative to fuselage datum (positive = leading edge up)"
- Tooltip: "Tilts the wing up or down relative to the body. Positive values tilt the front of the wing up. Most planes use 1-3 degrees."

---

## 6. Additional UX Observations

### 6a. The Two "Span" Fields Need Clearer Labels

The aero doc confirms the mockup's two "SPAN" fields map to Wing Span (G03) and Tail Span (G04). In the current mockup, they are both labeled just "SPAN" which is ambiguous. The labels must be:
- **Wing Span** (or just show the wing icon + "Span")
- **Tail Span** (or tail icon + "Span")

### 6b. Chord Field Ambiguity

The mockup shows a single "CHORD" field in the Global panel, but the aero doc defines both Root Chord (W02/G05) and Tip Chord (W03) with Tip/Root Ratio (W04) linking them. For the Global panel, showing only Root Chord (labeled "Wing Chord") is correct -- tip chord is derived from it via the ratio in the wing component panel. This matches the aero doc's scope assignments.

But consider: should the Global panel show TWO chord fields (Root and Tip) as it does two span fields? The mockup shows "CHORD: [ ] [ ]" which could be root and tip side by side. If so, changing either chord value should auto-update Tip/Root Ratio in the wing component panel. This would be a useful shortcut for quick planform definition.

**Recommendation:** Show Root Chord and Tip Chord side by side in the Global panel (matching the two-field layout for Engines). The Tip/Root Ratio in the wing component panel becomes purely derived.

### 6c. Print Settings Organization

The aero doc defines 24 print/fabrication parameters (PR01-PR24). These should be organized into a dedicated "Print Settings" panel or dialog, NOT mixed into the component panels. Proposed structure:

**Printer Setup (set once, persisted):**
- Nozzle Diameter (PR06)
- Layer Height (PR07)
- Print Bed X/Y/Z (PR01-PR03)

**Part Generation (per-export):**
- Auto-Section (PR04)
- Joint Type (PR10)
- Joint Overlap (PR05)
- Joint Tolerance (PR11)
- Hollow Parts (PR14)
- Spar Channels (PR15)

**Export (in export dialog):**
- Export Format (PR20)
- STL Tolerance (PR21)
- Per-Part Export (PR23)

### 6d. Fuselage Length vs Overall Aircraft Length

The mockup shows "300.00" as a dimension annotation that appears to span the entire aircraft. The aero doc maps this to `fuselageLength` (F01). But the overall aircraft length includes the nose spinner and any tail extension beyond the fuselage. Consider adding a derived "Overall Length" annotation that includes spinner length and any tail overhang, separate from the editable fuselage length parameter.

---

## Summary of Actionable Items

| # | Item | Priority | Affects |
|---|------|----------|---------|
| 1 | Group component panel fields into labeled sub-sections (Shape/Layout, Planform/Profile) | High | UX doc Section 2.4 |
| 2 | Move print params (except wall thickness) to dedicated Print Settings section | High | UX doc Section 2, Aero doc Section 9 |
| 3 | Implement primary/derived toggle pattern for bidirectional params (Tip Chord/Ratio, Dihedral/Angle) | High | Frontend implementation |
| 4 | Define animated show/hide transitions (150ms fade, 30ms stagger) for visibility dependencies | Medium | UX doc Section 3 |
| 5 | Rename 10 parameters for beginner-friendliness (see table in Section 5) | Medium | Aero doc labels, Frontend labels |
| 6 | Add tooltips for every parameter using simplified descriptions | Medium | Frontend implementation |
| 7 | Make Nozzle Diameter a persisted user preference, not a session parameter | Low | Architecture doc |
| 8 | Disambiguate "SPAN" labels in Global panel to "Wing Span" / "Tail Span" | High | Mockup update, Frontend |
| 9 | Show Root + Tip Chord side by side in Global panel (matching mockup's two-field layout) | Medium | UX doc Section 2.3 |
| 10 | Wall Thickness inputs should use nozzle-multiple stepper instead of free text | Medium | Frontend implementation |
| 11 | STL export is MVP -- already reflected in UX doc | Done | -- |
| 12 | Consolidate PR20/PR24 into a single format multi-select in Export dialog | Low | Aero doc cleanup |
