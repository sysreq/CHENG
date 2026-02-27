// ============================================================================
// CHENG — Dynamic Stability Analyzer
// Pure TypeScript utility for classifying dynamic mode quality.
// Based on MIL-F-8785C and FAR 23 flying-quality requirements.
// Issue #356
// ============================================================================

/**
 * Quality classification for a dynamic stability mode.
 * - 'good'       — meets Level 1 / desired flying qualities
 * - 'acceptable' — meets Level 2 / adequate flying qualities
 * - 'poor'       — fails Level 2 / unsatisfactory or dangerous
 * - 'unknown'    — data unavailable or outside classification range
 */
export type ModeQuality = 'good' | 'acceptable' | 'poor' | 'unknown';

/**
 * Classify the short-period mode quality.
 *
 * Boundaries (based on MIL-F-8785C Category B):
 * - Good:       0.35 ≤ ζ ≤ 1.30 and ωn > 1.0 rad/s
 * - Acceptable: 0.20 ≤ ζ < 0.35, or 1.30 < ζ ≤ 2.0, or ωn ≤ 1.0 (if ζ in range)
 * - Poor:       ζ < 0.20, or ζ > 2.0, or ωn ≤ 0
 *
 * @param zeta   Damping ratio (dimensionless).
 * @param omegaN Natural frequency (rad/s).
 */
export function classifyShortPeriod(zeta: number, omegaN: number): ModeQuality {
  if (!isFinite(zeta) || !isFinite(omegaN)) return 'unknown';
  if (omegaN <= 0) return 'poor';

  if (zeta < 0.20 || zeta > 2.0) return 'poor';

  const zetaGood = zeta >= 0.35 && zeta <= 1.30;
  const omegaGood = omegaN >= 1.0;

  if (zetaGood && omegaGood) return 'good';

  // Acceptable: damping is in 0.20–0.35 or 1.30–2.0 range, or omega marginal
  return 'acceptable';
}

/**
 * Classify the phugoid mode quality.
 *
 * Boundaries (FAR 23 / MIL-F-8785C):
 * - Good:       ζ ≥ 0.04 (well-damped, pilot workload acceptable)
 * - Acceptable: 0 < ζ < 0.04 (lightly damped but stable oscillation)
 * - Poor:       ζ ≤ 0 (divergent or neutral)
 *
 * @param zeta Damping ratio (dimensionless).
 */
export function classifyPhugoid(zeta: number): ModeQuality {
  if (!isFinite(zeta)) return 'unknown';

  if (zeta >= 0.04) return 'good';
  if (zeta > 0) return 'acceptable';
  return 'poor';  // zeta <= 0: divergent
}

/**
 * Classify the Dutch roll mode quality.
 *
 * Boundaries (MIL-F-8785C):
 * - Good:       ζ ≥ 0.08 and ωn ≥ 0.4 rad/s
 * - Acceptable: 0.02 ≤ ζ < 0.08 (lightly damped but stable)
 * - Poor:       ζ < 0.02 or ζ < 0 (neutrally stable or divergent)
 *
 * @param zeta   Damping ratio (dimensionless).
 * @param omegaN Natural frequency (rad/s).
 */
export function classifyDutchRoll(zeta: number, omegaN: number): ModeQuality {
  if (!isFinite(zeta) || !isFinite(omegaN)) return 'unknown';

  if (zeta < 0) return 'poor';     // divergent
  if (zeta < 0.02) return 'poor';  // nearly neutral — unacceptable

  if (zeta >= 0.08) return 'good';
  return 'acceptable';  // 0.02 ≤ zeta < 0.08
}

/**
 * Classify the roll mode quality.
 *
 * Based on MIL-F-8785C Category B (normal flight):
 * - Good:       τ ≤ 0.5 s (fast roll response)
 * - Acceptable: 0.5 < τ ≤ 1.0 s (sluggish but controllable)
 * - Poor:       τ > 1.0 s (too sluggish for precision flying)
 *
 * @param tauS Time constant in seconds (must be > 0 for valid mode).
 */
export function classifyRollMode(tauS: number): ModeQuality {
  if (!isFinite(tauS) || tauS <= 0) return 'unknown';

  if (tauS <= 0.5) return 'good';
  if (tauS <= 1.0) return 'acceptable';
  return 'poor';
}

/**
 * Classify the spiral mode quality.
 *
 * Spiral divergence (t2 = time-to-double) boundaries:
 * - Good:       Stable (t2 = Infinity) or very slow divergence (t2 ≥ 20 s)
 * - Acceptable: 8 s ≤ t2 < 20 s (pilot can correct in time)
 * - Poor:       t2 < 8 s (too fast for pilot correction)
 *
 * @param t2S Time-to-double amplitude in seconds. Use Infinity for stable/convergent spiral.
 */
export function classifySpiralMode(t2S: number): ModeQuality {
  if (!isFinite(t2S)) return 'good';  // Infinity = stable

  if (t2S < 0) return 'good';         // negative t2 = convergent spiral
  if (t2S >= 20) return 'good';
  if (t2S >= 8) return 'acceptable';
  return 'poor';
}
