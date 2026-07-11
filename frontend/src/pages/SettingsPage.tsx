import {Tabs, Typography} from 'antd';
import {TeamsTab} from './settings/TeamsTab';
import {BlocksTab} from './settings/BlocksTab';
import {SegmentsTab} from './settings/SegmentsTab';
import {FreezeDaysTab} from './settings/FreezeDaysTab';
import {UsersTab} from './settings/UsersTab';

const SETTINGS_TAB_KEY = 'settingsActiveTab';

export function SettingsPage() {
  const savedTab = localStorage.getItem(SETTINGS_TAB_KEY);

  return (
    <>
      <Typography.Title level={2}>Настройки</Typography.Title>
      <Tabs
        defaultActiveKey={savedTab ?? 'teams'}
        onChange={(key) => localStorage.setItem(SETTINGS_TAB_KEY, key)}
        items={[
          { key: 'teams', label: 'Команды', children: <TeamsTab /> },
          { key: 'blocks', label: 'Блоки и шаблоны', children: <BlocksTab /> },
          { key: 'segments', label: 'Сегменты', children: <SegmentsTab /> },
          { key: 'freeze', label: 'Дни фриза', children: <FreezeDaysTab /> },
          { key: 'users', label: 'Пользователи', children: <UsersTab /> },
        ]}
      />
    </>
  );
}
