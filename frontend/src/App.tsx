import { useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDesignSync } from '@/hooks/useDesignSync';
import { useConnectionStore } from '@/store/connectionStore';
import { useChengMode } from '@/hooks/useChengMode';
import { useIndexedDbPersistence } from '@/hooks/useIndexedDbPersistence';
import { Toolbar } from '@/components/Toolbar';
import Scene from '@/components/Viewport/Scene';
import { ComponentPanel } from '@/components/panels/ComponentPanel';
import ConnectionStatus from '@/components/ConnectionStatus';
import DisconnectedBanner from '@/components/DisconnectedBanner';
import ColdStartOverlay from '@/components/ColdStartOverlay';
import { ExportDialog } from '@/components/ExportDialog';
import StorageUsageIndicator from '@/components/StorageUsageIndicator';

/**
 * Root application layout (updated for #221, #289):
 *
 * +------------------------------------------+
 * |  TOOLBAR (File / Edit / Presets)         |
 * +------------------------------------------+
 * |                                          |
 * |            3D VIEWPORT                   |
 * |                                          |
 * +------------------------------------------+
 * |  COMPONENT PANEL                         |
 * |  (tabs: Global / Wing / Tail / ...)      |
 * +------------------------------------------+
 * |  STATUS BAR                              |
 * +------------------------------------------+
 *
 * The previous right-sidebar GlobalPanel has been inlined as the first tab
 * ("Global") in ComponentPanel. Presets are now in the top menu bar.
 *
 * In cloud mode (#150) IndexedDB persistence is active and a storage-usage
 * indicator is shown in the status bar.
 *
 * Responsive layout (#157): minimum supported size is 1280x720.
 * - min-width: 1280px enforced on the root container
 * - Component panel height is capped at 40vh (≈288px at 720px) so the
 *   viewport retains at least ~350px of usable vertical space
 * - Toolbar right section collapses verbose items below ~1440px via CSS
 */
export default function App() {
  const { send } = useWebSocket();
  useDesignSync(send);

  // Discover CHENG_MODE from the backend (/api/mode)
  const { mode: chengMode } = useChengMode();
  const isCloudMode = chengMode === 'cloud';

  // Enable IndexedDB auto-save + restore in cloud mode
  useIndexedDbPersistence(isCloudMode);

  const [exportOpen, setExportOpen] = useState(false);
  const isConnected = useConnectionStore((s) => s.state === 'connected');

  // When disconnected, dim panels visually but keep them scrollable (#194).
  // Individual inputs are disabled via the disabled prop (#178).
  const panelStyle = !isConnected
    ? { opacity: 0.5 }
    : {};

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr',
        gridTemplateRows: '1fr auto var(--statusbar-height)',
        height: '100vh',
        // Use CSS custom properties so the breakpoints stay in one place (index.css)
        minHeight: 'var(--min-app-height)',
        minWidth: 'var(--min-app-width)',
        overflow: 'hidden',
      }}
    >
      {/* Center — 3D Viewport */}
      <main
        style={{
          gridColumn: '1',
          gridRow: '1',
          position: 'relative',
          overflow: 'hidden',
          backgroundColor: 'var(--color-bg-secondary)',
          // Ensure the viewport retains a reasonable minimum height at 720px.
          // 720 - 40(toolbar) - 40vh(panel@720=288) - 32(statusbar) ≈ 360px
          minHeight: '200px',
        }}
      >
        <Toolbar onOpenExport={() => setExportOpen(true)} />
        <DisconnectedBanner />
        <div style={{ position: 'absolute', inset: 0, top: 'var(--toolbar-height)' }}>
          <Scene />
        </div>
        {/* Cold start overlay -- shown on slow initial connection (e.g. Cloud Run) */}
        <ColdStartOverlay />
      </main>

      {/* Bottom — Component Panel (Global / Wing / Tail / Fuselage / Landing Gear) */}
      <section
        className="component-panel-section"
        style={{
          gridColumn: '1',
          gridRow: '2',
          backgroundColor: 'var(--color-bg-tertiary)',
          borderTop: '1px solid var(--color-border)',
          overflowY: 'auto',
          // Responsive panel height: cap at 40vh so the 3D viewport retains
          // at least ~350px of vertical space at 720px screen height.
          maxHeight: 'min(320px, 40vh)',
          position: 'relative',
          ...panelStyle,
        }}
      >
        <fieldset disabled={!isConnected} style={{ border: 'none', padding: 0, margin: 0 }}>
          <ComponentPanel />
        </fieldset>
      </section>

      {/* Bottom Bar — status */}
      <footer
        style={{
          gridColumn: '1',
          gridRow: '3',
          backgroundColor: 'var(--color-bg-tertiary)',
          borderTop: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '0 12px',
          fontSize: '12px',
        }}
      >
        {/* Storage usage shown only in cloud mode (#150) */}
        <StorageUsageIndicator visible={isCloudMode} />
        <ConnectionStatus />
      </footer>

      {/* Modal overlay */}
      <ExportDialog open={exportOpen} onOpenChange={setExportOpen} />
    </div>
  );
}
