import { useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDesignSync } from '@/hooks/useDesignSync';
import { useConnectionStore } from '@/store/connectionStore';
import { Toolbar } from '@/components/Toolbar';
import Scene from '@/components/Viewport/Scene';
import { ComponentPanel } from '@/components/panels/ComponentPanel';
import ConnectionStatus from '@/components/ConnectionStatus';
import DisconnectedBanner from '@/components/DisconnectedBanner';
import ColdStartOverlay from '@/components/ColdStartOverlay';
import { ExportDialog } from '@/components/ExportDialog';

/**
 * Root application layout (updated for #289):
 *
 * +------------------------------------------+
 * |  TOOLBAR (File / Edit / Presets / View)  |
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
 */
export default function App() {
  const { send } = useWebSocket();
  useDesignSync(send);

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
        style={{
          gridColumn: '1',
          gridRow: '2',
          backgroundColor: 'var(--color-bg-tertiary)',
          borderTop: '1px solid var(--color-border)',
          overflowY: 'auto',
          maxHeight: '320px',
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
        <ConnectionStatus />
      </footer>

      {/* Modal overlay */}
      <ExportDialog open={exportOpen} onOpenChange={setExportOpen} />
    </div>
  );
}
