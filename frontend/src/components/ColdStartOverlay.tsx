// ============================================================================
// CHENG — Cold Start Overlay
// Spec: ux_design.md §1.3
// ============================================================================

import { useColdStart } from '@/hooks/useColdStart';
import type { ColdStartPhase } from '@/hooks/useColdStart';

const PHASE_TEXT: Partial<Record<ColdStartPhase, string>> = {
  starting: 'Starting design engine…',
  loading: 'Loading airfoil database…',
  initializing: 'Initializing geometry kernel…',
  ready: 'Ready!',
};

const PHASE_PROGRESS: Partial<Record<ColdStartPhase, number>> = {
  starting: 20,
  loading: 50,
  initializing: 80,
  ready: 100,
};

const COLD_START_STYLES = `
  :root { --skeleton-base: rgba(128, 128, 128, 0.25); --skeleton-track: rgba(128, 128, 128, 0.15); }
  @keyframes skeletonShimmer { 0%, 100% { opacity: 0.5; } 50% { opacity: 1; } }
  @keyframes spinnerRotate { to { transform: rotate(360deg); } }
  @keyframes coldStartFadeIn { from { opacity: 0; } to { opacity: 1; } }
`;

function SkeletonPlane() {
  return <div aria-hidden='true' style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, width: 260 }}>
    <div style={{ width: 200, height: 28, borderRadius: 14, background: 'var(--skeleton-base)', animation: 'skeletonShimmer 1.6s ease-in-out infinite' }} />
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 100, height: 14, borderRadius: 7, background: 'var(--skeleton-base)', animation: 'skeletonShimmer 1.6s ease-in-out infinite 0.2s', transform: 'skewY(-6deg)' }} />
      <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'var(--skeleton-base)', animation: 'skeletonShimmer 1.6s ease-in-out infinite 0.1s' }} />
      <div style={{ width: 100, height: 14, borderRadius: 7, background: 'var(--skeleton-base)', animation: 'skeletonShimmer 1.6s ease-in-out infinite 0.2s', transform: 'skewY(6deg)' }} />
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 48, height: 10, borderRadius: 5, background: 'var(--skeleton-base)', animation: 'skeletonShimmer 1.6s ease-in-out infinite 0.4s' }} />
      <div style={{ width: 12, height: 30, borderRadius: 6, background: 'var(--skeleton-base)', animation: 'skeletonShimmer 1.6s ease-in-out infinite 0.3s' }} />
      <div style={{ width: 48, height: 10, borderRadius: 5, background: 'var(--skeleton-base)', animation: 'skeletonShimmer 1.6s ease-in-out infinite 0.4s' }} />
    </div>
  </div>;
}

function ProgressBar({ phase }: { phase: ColdStartPhase }) {
  const pct = PHASE_PROGRESS[phase] ?? 0;
  return <div role='progressbar' aria-label='Loading progress' aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} style={{ width: 260, height: 3, borderRadius: 2, background: 'var(--skeleton-track)', overflow: 'hidden' }}>
    <div style={{ height: '100%', width: `${pct}%`, background: 'var(--color-accent, #3b82f6)', borderRadius: 2, transition: 'width 0.8s ease' }} />
  </div>;
}

function Spinner() {
  return <div aria-hidden='true' style={{ width: 24, height: 24, border: '2.5px solid var(--skeleton-base)', borderTopColor: 'var(--color-accent, #3b82f6)', borderRadius: '50%', animation: 'spinnerRotate 0.8s linear infinite', flexShrink: 0 }} />;
}

/**
 * Cold start overlay -- shown when the initial WebSocket connection is slow.
 *
 * Renders skeleton airplane shimmer, explanatory text, and a progress bar
 * while waiting for the Cloud Run backend to cold-start (5-15 seconds).
 * Only activates on first app load. Does NOT show on reconnects.
 * Dismissed automatically once connected and first mesh is received.
 */
export default function ColdStartOverlay() {
  const { visible, phase } = useColdStart();
  if (!visible) return null;
  const phaseText = PHASE_TEXT[phase] ?? 'Starting…';
  const isReady = phase === 'ready';
  return (
    <>
      <style>{COLD_START_STYLES}</style>
      <div
        role='status'
        aria-live='polite'
        aria-label='Application is starting up'
        data-testid='cold-start-overlay'
        style={{
          position: 'absolute', inset: 0, zIndex: 50,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 24,
          backgroundColor: 'var(--color-bg-secondary, #111)',
          animation: 'coldStartFadeIn 0.3s ease',
        }}
      >
        <SkeletonPlane />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minHeight: 28 }}>
          {!isReady && <Spinner />}
          <span style={{ fontSize: 13, fontWeight: 500, color: isReady ? 'var(--color-success, #22c55e)' : 'var(--color-text-secondary, #9ca3af)', transition: 'color 0.3s ease' }}>
            {phaseText}
          </span>
        </div>
        <p style={{ fontSize: 11, color: 'var(--color-text-muted, #6b7280)', textAlign: 'center', maxWidth: 300, lineHeight: 1.5, margin: 0 }}>
          Starting up... Cloud instances may take 5-15 seconds on first load.
        </p>
        <ProgressBar phase={phase} />
      </div>
    </>
  );
}
