import { useState } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDesignSync } from '@/hooks/useDesignSync';
import { Toolbar } from '@/components/Toolbar';
import Scene from '@/components/Viewport/Scene';
import { GlobalPanel } from '@/components/panels/GlobalPanel';
import { ComponentPanel } from '@/components/panels/ComponentPanel';
import ConnectionStatus from '@/components/ConnectionStatus';
import { ExportDialog } from '@/components/ExportDialog';

/**
 * Root application layout.
 *
 * CSS Grid with three areas:
 * - Left sidebar (320px): GlobalPanel + ComponentPanel
 * - Center: 3D viewport (flex)
 * - Bottom bar: Toolbar + ConnectionStatus
 */
export default function App() {
  const { send } = useWebSocket();
  useDesignSync(send);

  const [exportOpen, setExportOpen] = useState(false);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'var(--sidebar-width) 1fr',
        gridTemplateRows: '1fr var(--statusbar-height)',
        height: '100vh',
        overflow: 'hidden',
      }}
    >
      {/* Left Sidebar — panels */}
      <aside
        style={{
          gridColumn: '1',
          gridRow: '1',
          backgroundColor: 'var(--color-bg-secondary)',
          borderRight: '1px solid var(--color-border)',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <GlobalPanel />
        <ComponentPanel />
      </aside>

      {/* Center — 3D Viewport */}
      <main
        style={{
          gridColumn: '2',
          gridRow: '1',
          position: 'relative',
          overflow: 'hidden',
          backgroundColor: 'var(--color-bg-secondary)',
        }}
      >
        <Toolbar onOpenExport={() => setExportOpen(true)} />
        <div style={{ position: 'absolute', inset: 0, top: 'var(--toolbar-height)' }}>
          <Scene />
        </div>
      </main>

      {/* Bottom Bar — status */}
      <footer
        style={{
          gridColumn: '1 / -1',
          gridRow: '2',
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
