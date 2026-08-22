import {createContext, type ReactNode, useContext, useState} from 'react';
import {Button, Empty, Space, Spin, Typography} from 'antd';

export interface NotificationAction {
  label: string;
  onClick: () => void;
  primary?: boolean;
  loading?: boolean;
}

const NotificationCenterContext = createContext({closeCenter: () => {}});

export const NotificationCenterProvider = NotificationCenterContext.Provider;
export const useNotificationCenter = () => useContext(NotificationCenterContext);

export function useDeferredDrawerNavigation<T>(closeDrawer: () => void, navigate: (item: T) => void) {
  const [pending, setPending] = useState<T | null>(null);
  return {
    selectFromDrawer: (item: T) => {
      setPending(item);
      closeDrawer();
    },
    afterOpenChange: (open: boolean) => {
      if (open || pending === null) return;
      const item = pending;
      setPending(null);
      navigate(item);
    },
  };
}

export function NotificationTabPanel({children, shown, total, loading, error, emptyText, actions = []}: {
  children: ReactNode;
  shown: number;
  total: number;
  loading?: boolean;
  error?: boolean;
  emptyText: string;
  actions?: NotificationAction[];
}) {
  return <div style={{maxHeight: 'calc(100vh - 180px)', overflowY: 'auto'}}>
    {loading ? <div style={{textAlign: 'center', padding: '16px 0'}}><Spin size="small"/></div> :
      error ? <Typography.Text type="danger">Не удалось загрузить</Typography.Text> :
        shown === 0 ? <Empty description={emptyText} image={Empty.PRESENTED_IMAGE_SIMPLE}/> : <>
          {children}
          {total > shown && <Typography.Text type="secondary"
            style={{display: 'block', marginTop: 8, fontSize: '0.8rem'}}>
            Показаны первые {shown} из {total}
          </Typography.Text>}
          {actions.length > 0 && <Space style={{marginTop: 8}} wrap>
            {actions.map((action) => <Button key={action.label} type={action.primary ? 'primary' : 'default'}
              loading={action.loading} onClick={action.onClick}>{action.label}</Button>)}
          </Space>}
        </>}
  </div>;
}
