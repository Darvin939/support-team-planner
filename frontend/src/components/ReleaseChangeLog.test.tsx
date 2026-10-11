// @vitest-environment jsdom

import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {AppShell} from './AppShell';
import {ReleaseChangeLogExperience} from './ReleaseChangeLog';
import type {ReleaseChangeLogData} from '../hooks/useReleaseChangeLog';

vi.mock('./OverdueNotifications', () => ({OverdueNotifications: () => null}));

const data: ReleaseChangeLogData = {
  application: {release_version: '1.2.0', build_id: '20261011T143012Z-ab12cd34'},
  releases: [
    {version: '1.2.0', date: '2026-10-11', title: 'Планирование', changes: ['Новое действие в плане']},
    {version: '1.1.0', date: '2026-09-01', title: 'Уведомления', changes: ['Появились уведомления']},
  ],
  unseen_releases: [{
    version: '1.2.0', date: '2026-10-11', title: 'Планирование', changes: ['Новое действие в плане'],
  }],
};

describe('журнал изменений релизов', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false, addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    })));
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('показывает версию и build id в подвале сайдбара и открывает историю', () => {
    const onOpenReleaseHistory = vi.fn();
    render(<AppShell activePath="/planning" isDark={false} role="user" login="reader" userName="Читатель"
      onToggleTheme={vi.fn()} onNavigate={vi.fn()} onLogout={vi.fn()} onOpenProfile={vi.fn()}
      applicationMetadata={data.application} onOpenReleaseHistory={onOpenReleaseHistory}>
      <div>Содержимое</div>
    </AppShell>);

    expect(screen.getByText('v1.2.0 · 20261011T143012Z-ab12cd34')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Открыть историю изменений'}));
    expect(onOpenReleaseHistory).toHaveBeenCalledOnce();
  });

  it('открывает полную историю по версиям и датам', async () => {
    render(<ReleaseChangeLogExperience data={{...data, unseen_releases: []}} isLoading={false}
      isAcknowledging={false} markSeen={vi.fn().mockResolvedValue(undefined)}>
      {({openHistory}) => <button onClick={openHistory}>Открыть историю</button>}
    </ReleaseChangeLogExperience>);
    fireEvent.click(screen.getByRole('button', {name: 'Открыть историю'}));

    expect(await screen.findByText('История изменений')).toBeTruthy();
    expect(screen.getByText('2026-10-11')).toBeTruthy();
    expect(screen.getByText('v1.2.0')).toBeTruthy();
    expect(screen.getByText('2026-09-01')).toBeTruthy();
    expect(screen.getByText('v1.1.0')).toBeTruthy();
  });

  it('показывает накопленную сводку и отмечает все показанные релизы по кнопке', async () => {
    const markSeen = vi.fn().mockResolvedValue(undefined);
    render(<ReleaseChangeLogExperience data={{...data, unseen_releases: data.releases}} isLoading={false}
      isAcknowledging={false} markSeen={markSeen}>
      {() => <div/>}
    </ReleaseChangeLogExperience>);

    expect(await screen.findByText('Что нового')).toBeTruthy();
    expect(screen.getByText('Новое действие в плане')).toBeTruthy();
    expect(screen.getByText('Появились уведомления')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', {name: 'Понятно'}));
    await waitFor(() => expect(markSeen).toHaveBeenCalledWith(['1.2.0', '1.1.0']));
  });

  it('закрытие окна тоже подтверждает просмотр всех записей в нём', async () => {
    const markSeen = vi.fn().mockResolvedValue(undefined);
    render(<ReleaseChangeLogExperience data={data} isLoading={false} isAcknowledging={false} markSeen={markSeen}>
      {() => <div/>}
    </ReleaseChangeLogExperience>);
    await screen.findByText('Что нового');
    fireEvent.click(screen.getByRole('button', {name: 'Close'}));
    await waitFor(() => expect(markSeen).toHaveBeenCalledWith(['1.2.0']));
  });

  it('не открывает автоматическую сводку, если непросмотренных релизов нет', async () => {
    render(<ReleaseChangeLogExperience data={{...data, unseen_releases: []}} isLoading={false}
      isAcknowledging={false} markSeen={vi.fn().mockResolvedValue(undefined)}>
      {() => <div/>}
    </ReleaseChangeLogExperience>);
    await waitFor(() => expect(screen.queryByText('Что нового')).toBeNull());
  });
});
