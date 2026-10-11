import {useEffect, useState} from 'react';
import {Outlet, useLocation, useNavigate} from 'react-router-dom';
import {Spin} from 'antd';
import {AppShell} from './AppShell';
import {MyAccountModal} from './MyAccountModal';
import {useMe} from '../hooks/useMe';
import {formatDisplayName} from '../hooks/useUserNames';
import {useMarkReleaseVersionsSeen, useReleaseChangeLog} from '../hooks/useReleaseChangeLog';
import {ReleaseChangeLogExperience} from './ReleaseChangeLog';

export function AuthenticatedLayout({isDark, onToggleTheme}: { isDark: boolean; onToggleTheme: () => void }) {
  const {data: me, isLoading, isError} = useMe();
  const navigate = useNavigate();
  const location = useLocation();
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const releaseChangeLog = useReleaseChangeLog();
  const markReleaseVersionsSeen = useMarkReleaseVersionsSeen();

  useEffect(() => {
    // Сессия истекла/недействительна, пока SPA уже открыт — ведём себя как обычный
    // редирект require_login на полной загрузке страницы.
    if (isError) window.location.href = '/login';
  }, [isError]);

  if (isLoading || !me) {
    return (
      <div style={{minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <Spin size="large"/>
      </div>
    );
  }

  const basePath = '/' + location.pathname.split('/')[1];

  async function handleLogout() {
    await fetch('/logout', {method: 'POST', credentials: 'same-origin'});
    window.location.href = '/login';
  }

  return (
    <>
      <ReleaseChangeLogExperience
        data={releaseChangeLog.data}
        isLoading={releaseChangeLog.isLoading}
        isAcknowledging={markReleaseVersionsSeen.isPending}
        markSeen={(versions) => markReleaseVersionsSeen.mutateAsync(versions)}
      >
        {({application, openHistory}) => <AppShell
          activePath={basePath}
          isDark={isDark}
          role={me.role}
          login={me.login ?? null}
          userName={formatDisplayName(me)}
          onToggleTheme={onToggleTheme}
          onNavigate={navigate}
          onLogout={handleLogout}
          onOpenProfile={() => setProfileModalOpen(true)}
          applicationMetadata={application}
          onOpenReleaseHistory={openHistory}
        >
          <Outlet/>
        </AppShell>}
      </ReleaseChangeLogExperience>
      <MyAccountModal open={profileModalOpen} onClose={() => setProfileModalOpen(false)}/>
    </>
  );
}
