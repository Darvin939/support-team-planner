import type {ReactNode} from 'react';
import type {MenuProps} from 'antd';
import {Layout, Menu} from 'antd';
import {chrome} from '../theme';

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

export function AppShell({
  children,
  activePath,
  isDark,
  role,
  onToggleTheme,
  onNavigate,
  onLogout,
}: {
  children: ReactNode;
  activePath: string;
  isDark: boolean;
  role: string | null;
  onToggleTheme: () => void;
  onNavigate: (path: string) => void;
  onLogout: () => void;
}) {
  const c = isDark ? chrome.dark : chrome.light;

  const navItems: MenuProps['items'] = [
    { key: '/planning', icon: <GridIcon />, label: 'Планирование' },
    { key: '/statistics', icon: <ChartIcon />, label: 'Статистика' },
    { key: '/journal', icon: <ClockIcon />, label: 'Журнал изменений' },
    ...(role === 'admin' || role === 'editor' ? [{ key: '/settings', icon: <GearIcon />, label: 'Настройки' }] : []),
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Sider
        width={216}
        style={{ background: c.bg, position: 'fixed', top: 0, left: 0, bottom: 0, overflow: 'auto' }}
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
        <Menu
          mode="inline"
          selectedKeys={[activePath]}
          items={navItems}
          onClick={({ key }) => onNavigate(key)}
          style={{ background: 'transparent', border: 'none' }}
          theme={isDark ? 'dark' : 'light'}
        />
        <div style={{ position: 'absolute', bottom: 0, width: '100%', padding: 10, display: 'flex', flexDirection: 'column', gap: 2 }}>
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
      <Layout style={{ marginLeft: 216 }}>
        <Layout.Content style={{ padding: 24, maxWidth: 1400, margin: '0 auto', width: '100%' }}>
          {children}
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
