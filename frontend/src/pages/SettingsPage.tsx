import {Tabs, Typography} from 'antd';
import {TeamsTab} from './settings/TeamsTab';
import {WorkReferencesTab} from './settings/BlocksTab';
import {FreezeDaysTab} from './settings/FreezeDaysTab';
import {UsersTab} from './settings/UsersTab';

const SETTINGS_TAB_KEY = 'settingsActiveTab';
const SETTINGS_TAB_KEYS = new Set(['teams', 'references', 'freeze', 'users']);

function getInitialTab(): string {
  const savedTab = localStorage.getItem(SETTINGS_TAB_KEY);
  if (savedTab === 'blocks' || savedTab === 'segments') return 'references';
  return savedTab && SETTINGS_TAB_KEYS.has(savedTab) ? savedTab : 'teams';
}

export function SettingsPage() {
  return (
    <>
      <Typography.Title level={2}>Настройки</Typography.Title>
      <Tabs
        defaultActiveKey={getInitialTab()}
        onChange={(key) => localStorage.setItem(SETTINGS_TAB_KEY, key)}
        items={[
          {key: 'teams', label: 'Команды', children: <TeamsTab/>},
          {key: 'references', label: 'Справочники работ', children: <WorkReferencesTab/>},
          {key: 'freeze', label: 'Дни фриза', children: <FreezeDaysTab/>},
          {key: 'users', label: 'Пользователи', children: <UsersTab/>},
        ]}
      />
    </>
  );
}
