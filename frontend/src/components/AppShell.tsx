import {type ReactNode, useEffect, useState} from 'react';
import type {MenuProps} from 'antd';
import {Layout, Menu} from 'antd';
import {chrome} from '../theme';
import {useIsMobile} from '../hooks/useIsMobile';
import {OverdueNotifications} from './OverdueNotifications';

const TOP_BAR_HEIGHT = 56;

const iconStyle = { width: 17, height: 17, display: 'inline-flex' } as const;

function GridIcon() {
  return (
    <span style={iconStyle}>
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="14" height="13" rx="2" />
        <path d="M3 8h14M7 4v13" />
      </svg>
    </span>
  );
}

function ChartIcon() {
  return (
    <span style={iconStyle}>
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 16.5V10M10 16.5V3.5M16 16.5v-6" />
      </svg>
    </span>
  );
}

function ClockIcon() {
  return (
    <span style={iconStyle}>
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="10" cy="10.5" r="6.5" />
        <path d="M10 7v3.5l2.4 1.4" />
      </svg>
    </span>
  );
}

function GearIcon() {
  return (
    <span style={iconStyle}>
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="10" cy="10" r="2.6" />
        <path d="M10 3.6v1.6M10 14.8v1.6M16.4 10h-1.6M5.2 10H3.6M14.5 5.5l-1.1 1.1M6.6 13.3l-1.1 1.1M14.5 14.5l-1.1-1.1M6.6 6.7 5.5 5.6" />
      </svg>
    </span>
  );
}

function LogoutIcon() {
  return (
    <span style={iconStyle}>
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 3.5H4.8A1.3 1.3 0 0 0 3.5 4.8v10.4a1.3 1.3 0 0 0 1.3 1.3H8" />
        <path d="M13 13.5l3.5-3.5L13 6.5M7.5 10h9" />
      </svg>
    </span>
  );
}

function BurgerIcon() {
  return (
    <span style={iconStyle}>
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 5.5h14M3 10h14M3 14.5h14" />
      </svg>
    </span>
  );
}

export function AppShell({
  children,
  activePath,
  isDark,
  role,
  userName,
  onToggleTheme,
  onNavigate,
  onLogout,
  onOpenProfile,
}: {
  children: ReactNode;
  activePath: string;
  isDark: boolean;
  role: string | null;
  userName: string;
  onToggleTheme: () => void;
  onNavigate: (path: string) => void;
  onLogout: () => void;
  onOpenProfile: () => void;
}) {
  const c = isDark ? chrome.dark : chrome.light;
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!isMobile) setSidebarOpen(false);
  }, [isMobile]);

  useEffect(() => {
    if (!sidebarOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setSidebarOpen(false);
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [sidebarOpen]);

  function handleNavigate(path: string) {
    setSidebarOpen(false);
    onNavigate(path);
  }

  const navItems: MenuProps['items'] = [
    { key: '/planning', icon: <GridIcon />, label: 'Планирование' },
    { key: '/statistics', icon: <ChartIcon />, label: 'Статистика' },
    { key: '/journal', icon: <ClockIcon />, label: 'Журнал изменений' },
    ...(role === 'admin' || role === 'editor' ? [{ key: '/settings', icon: <GearIcon />, label: 'Настройки' }] : []),
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.45)', zIndex: 999 }}
        />
      )}
      {isMobile && (
        <div
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, height: TOP_BAR_HEIGHT, zIndex: 998,
            background: c.bg, color: c.text, display: 'flex', alignItems: 'center', gap: 12, padding: '0 16px',
          }}
        >
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            aria-expanded={sidebarOpen}
            style={{ background: 'none', border: 'none', color: c.text, cursor: 'pointer', display: 'flex', padding: 4 }}
          >
            <BurgerIcon />
          </button>
          <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
            Пульт<span style={{ color: '#1668dc' }}>.</span>Планировщик
          </span>
          <span style={{ marginLeft: 'auto', display: 'flex' }}>
            <OverdueNotifications compact />
          </span>
        </div>
      )}
      <Layout.Sider
        width={216}
        style={{
          background: c.bg,
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
          overflow: 'auto',
          zIndex: 1000,
          transform: isMobile && !sidebarOpen ? 'translateX(-100%)' : 'translateX(0)',
          transition: 'transform 0.25s ease',
          boxShadow: isMobile && sidebarOpen ? '0 0 24px rgba(0, 0, 0, 0.35)' : undefined,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '18px 18px 16px', color: c.text, fontWeight: 700, fontSize: '0.95rem' }}>
          <span style={iconStyle}>
            <svg viewBox="0 0 20 20" fill="none" stroke="#1668dc" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="14" height="14" rx="3" />
              <path d="M3 8.5h14M8.2 3v14" />
            </svg>
          </span>
          <span>
            Пульт<span style={{ color: '#1668dc' }}>.</span>Планировщик
          </span>
        </div>
        <div style={{ padding: '0 14px 10px', color: c.text }}>
          <OverdueNotifications />
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activePath]}
          items={navItems}
          onClick={({ key }) => handleNavigate(key)}
          style={{ background: 'transparent', border: 'none' }}
          theme={isDark ? 'dark' : 'light'}
        />
        <div style={{ position: 'absolute', bottom: 0, width: '100%', padding: 10, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <button
            onClick={onOpenProfile}
            title="Изменить пароль"
            style={{
              display: 'block', width: '100%', padding: '4px 10px 8px', background: 'none', border: 'none',
              color: c.text, fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer', textAlign: 'left',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}
          >
            {userName}
          </button>
          <button
            onClick={onToggleTheme}
            style={{
              display: 'flex', alignItems: 'center', gap: 11, width: '100%', padding: '8px 10px',
              background: 'none', border: 'none', color: c.text, cursor: 'pointer', textAlign: 'left', fontSize: '0.88rem',
            }}
          >
            {isDark ? '☾' : '☀'} {isDark ? 'Тёмная тема' : 'Светлая тема'}
          </button>
          <button
            onClick={onLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: 11, width: '100%', padding: '8px 10px',
              background: 'none', border: 'none', color: c.text, cursor: 'pointer', textAlign: 'left', fontSize: '0.88rem',
            }}
          >
            <LogoutIcon /> Выйти
          </button>
        </div>
      </Layout.Sider>
      <Layout style={{ marginLeft: isMobile ? 0 : 216 }}>
        <Layout.Content style={{ padding: 24, paddingTop: isMobile ? TOP_BAR_HEIGHT + 24 : 24, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
          {children}
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
