// ============================================================================
// CHENG — 3D Viewport Scene
// ============================================================================

import { Component, useState, useCallback, useEffect, useRef } from 'react';
import type { ReactNode, ErrorInfo } from 'react';
import { Canvas } from '@react-three/fiber';
import { Bounds, useBounds, Html } from '@react-three/drei';
import AircraftMesh from './AircraftMesh';
import Controls from './Controls';
import Annotations from './Annotations';
import { useDesignStore } from '@/store/designStore';

// ---------------------------------------------------------------------------
// Error Boundary for 3D Viewport (#179)
// ---------------------------------------------------------------------------

interface ViewportErrorBoundaryProps {
  children: ReactNode;
}

interface ViewportErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ViewportErrorBoundary extends Component<ViewportErrorBoundaryProps, ViewportErrorBoundaryState> {
  constructor(props: ViewportErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ViewportErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[Viewport] Render error:', error, info.componentStack);
  }

  handleReload = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#2A2A2E',
          color: '#ccc',
          fontFamily: 'monospace',
          gap: 12,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#ef4444' }}>
            3D Viewport Error
          </div>
          <div style={{ fontSize: 11, color: '#888', maxWidth: 400, textAlign: 'center' }}>
            {this.state.error?.message ?? 'An unexpected error occurred in the 3D renderer.'}
          </div>
          <button
            onClick={this.handleReload}
            style={{
              marginTop: 8,
              padding: '6px 16px',
              fontSize: 12,
              fontWeight: 600,
              color: '#fff',
              backgroundColor: '#3b82f6',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
            }}
          >
            Reload Viewport
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function BoundsWatcher({ readyTick }: { readyTick: number }) {
  const bounds = useBounds();

  useEffect(() => {
    if (readyTick > 0) {
      // Force a re-calculation of the boundaries and fit the camera
      bounds.refresh().clip().fit();

      const timer = setTimeout(() => {
        bounds.refresh().clip().fit();
      }, 150);

      return () => clearTimeout(timer);
    }
  }, [readyTick, bounds]);

  return null;
}

/** Delayed loading overlay — only shows after 300ms to avoid flicker. */
function GeneratingOverlay() {
  const isGenerating = useDesignStore((s) => s.isGenerating);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (isGenerating) {
      timerRef.current = setTimeout(() => setVisible(true), 300);
    } else {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
      setVisible(false);
    }
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [isGenerating]);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Generating 3D aircraft model"
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0, 0, 0, 0.35)',
        zIndex: 10,
        pointerEvents: 'none',
      }}
    >
      <div className="generating-spinner" aria-hidden="true" />
    </div>
  );
}

const AXIS_LABEL_STYLE: React.CSSProperties = {
  fontSize: 10,
  fontFamily: 'monospace',
  fontWeight: 700,
  whiteSpace: 'nowrap' as const,
  pointerEvents: 'none' as const,
  userSelect: 'none' as const,
};

/** Text labels for axes helper endpoints (#173). */
function AxesLabels({ size }: { size: number }) {
  return (
    <>
      <Html position={[size + 8, 0, 0]} center style={{ pointerEvents: 'none' }}>
        <span style={{ ...AXIS_LABEL_STYLE, color: '#ff4444' }}>X</span>
      </Html>
      <Html position={[0, size + 8, 0]} center style={{ pointerEvents: 'none' }}>
        <span style={{ ...AXIS_LABEL_STYLE, color: '#44ff44' }}>Y</span>
      </Html>
      <Html position={[0, 0, size + 8]} center style={{ pointerEvents: 'none' }}>
        <span style={{ ...AXIS_LABEL_STYLE, color: '#4444ff' }}>Z</span>
      </Html>
    </>
  );
}

export default function Scene() {
  const [readyTick, setReadyTick] = useState(0);
  const [contextLost, setContextLost] = useState(false);

  const handleMeshLoaded = useCallback(() => {
    setReadyTick((prev) => prev + 1);
  }, []);

  // Handle WebGL context loss (#179)
  const handleCreated = useCallback(({ gl }: { gl: { domElement: HTMLCanvasElement } }) => {
    const canvas = gl.domElement;
    canvas.addEventListener('webglcontextlost', (e) => {
      e.preventDefault();
      setContextLost(true);
      console.warn('[Viewport] WebGL context lost');
    });
    canvas.addEventListener('webglcontextrestored', () => {
      setContextLost(false);
      console.info('[Viewport] WebGL context restored');
    });
  }, []);

  if (contextLost) {
    return (
      <div style={{
        width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', backgroundColor: '#2A2A2E',
        color: '#ccc', fontFamily: 'monospace', gap: 12,
      }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#f59e0b' }}>WebGL Context Lost</div>
        <div style={{ fontSize: 11, color: '#888' }}>Waiting for the browser to restore the GPU context...</div>
      </div>
    );
  }

  return (
    <div
      style={{ width: '100%', height: '100%', position: 'relative' }}
      role="region"
      aria-label="3D aircraft viewport — use mouse to orbit, scroll to zoom, right-click to pan. Keyboard shortcuts: 1=Front, 2=Side, 3=Top, 4=Perspective."
      tabIndex={0}
    >
      <ViewportErrorBoundary>
        <Canvas
          gl={{ antialias: true }}
          camera={{ position: [500, 300, 500], fov: 50, near: 1, far: 10000 }}
          style={{ background: '#2A2A2E' }}
          onCreated={handleCreated}
          aria-label="3D aircraft model preview"
        >
          <ambientLight intensity={0.4} />
          <directionalLight position={[500, 500, 500]} intensity={0.8} />
          <directionalLight position={[-300, 200, -200]} intensity={0.3} />

          <gridHelper args={[2000, 40, '#555555', '#3a3a3a']} />
          <axesHelper args={[100]} />
          <AxesLabels size={100} />

          <Bounds fit observe margin={1.5}>
            <AircraftMesh onLoaded={handleMeshLoaded} />
            {readyTick > 0 && <BoundsWatcher readyTick={readyTick} />}
          </Bounds>
          <Controls />
        </Canvas>
      </ViewportErrorBoundary>

      <GeneratingOverlay />
      <Annotations onResetCamera={handleMeshLoaded} />
    </div>
  );
}