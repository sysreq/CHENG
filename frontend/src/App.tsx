import { useState, useCallback } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useDesignSync } from '@/hooks/useDesignSync';
import { useConnectionStore } from '@/store/connectionStore';
import { Toolbar } from '@/components/Toolbar';
import Scene from '@/components/Viewport/Scene';
import { GlobalPanel } from '@/components/panels/GlobalPanel';
import { ComponentPanel } from '@/components/panels/ComponentPanel';
import ConnectionStatus from '@/components/ConnectionStatus';
import DisconnectedBanner from '@/components/DisconnectedBanner';
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
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isConnected = useConnectionStore((s) => s.state === 'connected');

  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  // When disconnected, disable parameter panels (read-only mode)
  const panelStyle = !isConnected
    ? { opacity: 0.5, pointerEvents: 'none' as const }
    : {};

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
        <DisconnectedBanner />
        {/* Hamburger toggle for narrow viewports */}
        <button
          className="sidebar-toggle"
          onClick={toggleSidebar}
          aria-label="Toggle parameters panel"
          style={{
            position: 'absolute',
            top: 56,
            right: 12,
            zIndex: 20,
            width: 36,
            height: 36,
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 6,
            border: '1px solid var(--color-border)',
            backgroundColor: 'var(--color-bg-tertiary)',
            color: 'var(--color-text-primary)',
            cursor: 'pointer',
            fontSize: 18,
          }}
        >
          {sidebarOpen ? '\u2715' : '\u2630'}
        </button>
        <div style={{ position: 'absolute', inset: 0, top: 'var(--toolbar-height)' }}>
          <Scene />
        </div>
      </main>

      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="sidebar-backdrop"
          onClick={closeSidebar}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 25,
            backgroundColor: 'rgba(0,0,0,0.5)',
          }}
        />
      )}

      {/* Right Sidebar — Global Parameters */}
      <aside
        className={`app-sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}
        style={{
          gridColumn: '2',
          gridRow: '1 / 3',
          backgroundColor: 'var(--color-bg-secondary)',
          borderLeft: '1px solid var(--color-border)',
          overflowY: 'auto',
          ...panelStyle,
        }}
      >
        <div className="sticky top-0 z-10 px-3 py-2 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider bg-zinc-900/90 backdrop-blur border-b border-zinc-700/50">
          Parameters
        </div>
        <GlobalPanel />
      </aside>

      {/* Bottom-Left — Component Detail Panel */}
      <section
        style={{
          gridColumn: '1',
          gridRow: '2',
          backgroundColor: 'var(--color-bg-tertiary)',
          borderTop: '1px solid var(--color-border)',
          overflowY: 'auto',
          maxHeight: '280px',
          position: 'relative',
          ...panelStyle,
        }}
      >
        <div className="sticky top-0 z-10 px-3 py-2 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider bg-zinc-800/90 backdrop-blur border-b border-zinc-700/50">
          Component Details
        </div>
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
