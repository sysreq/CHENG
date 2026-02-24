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
 * Root application layout per UX spec Section 2.1:
 *
 * +---------------------------+-------------------+
 * |                           |  GLOBAL           |
 * |         VIEWPORT          |  PARAMETERS       |
 * |                           |  PANEL (right)    |
 * +---------------------------+-------------------+
 * |  COMPONENT DETAIL PANEL   |                   |
 * |  (bottom-left)            |   STATUS BAR      |
 * +---------------------------+-------------------+
 */
export default function App() {
  const { send } = useWebSocket();
  useDesignSync(send);

  const [exportOpen, setExportOpen] = useState(false);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr var(--sidebar-width)',
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
        <div style={{ position: 'absolute', inset: 0, top: 'var(--toolbar-height)' }}>
          <Scene />
        </div>
      </main>

      {/* Right Sidebar — Global Parameters */}
      <aside
        style={{
          gridColumn: '2',
          gridRow: '1 / 3',
          backgroundColor: 'var(--color-bg-secondary)',
          borderLeft: '1px solid var(--color-border)',
          overflowY: 'auto',
        }}
      >
        <GlobalPanel />
      </aside>

      {/* Bottom-Left — Component Detail Panel */}
      <section
        style={{
          gridColumn: '1',
          gridRow: '2',
          backgroundColor: 'var(--color-bg-secondary)',
          borderTop: '1px solid var(--color-border)',
          overflowY: 'auto',
          maxHeight: '280px',
        }}
      >
        <ComponentPanel />
      </section>

      {/* Bottom Bar — status */}
      <footer
        style={{
          gridColumn: '1 / -1',
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
