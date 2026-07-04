import {useEffect} from 'react';
import {Outlet, useLocation, useNavigate} from 'react-router-dom';
import {Spin} from 'antd';
import {AppShell} from './AppShell';
import {useMe} from '../hooks/useMe';

// Только эти пути уже перенесены на React в этом бандле — переход на остальные (ещё
// Jinja2-страницы) должен быть полной навигацией браузера, а не client-side роутингом.
const MIGRATED_BASE_PATHS = new Set(['/statistics', '/journal']);

export function AuthenticatedLayout({ isDark, onToggleTheme }: { isDark: boolean; onToggleTheme: () => void }) {
  const { data: me, isLoading, isError } = useMe();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Сессия истекла/недействительна, пока SPA уже открыт — ведём себя как обычный
    // редирект require_login на полной загрузке страницы.
    if (isError) window.location.href = '/login';
  }, [isError]);

  if (isLoading || !me) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  const basePath = '/' + location.pathname.split('/')[1];

  function handleNavigate(path: string) {
    if (MIGRATED_BASE_PATHS.has(path)) navigate(path);
    else window.location.href = path;
  }

  async function handleLogout() {
    await fetch('/logout', { method: 'POST', credentials: 'same-origin' });
    window.location.href = '/login';
  }

  return (
    <AppShell
      activePath={basePath}
      isDark={isDark}
      role={me.role}
      onToggleTheme={onToggleTheme}
      onNavigate={handleNavigate}
      onLogout={handleLogout}
    >
      <Outlet />
    </AppShell>
  );
}
