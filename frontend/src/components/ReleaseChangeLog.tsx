import {useEffect, useRef, useState, type ReactNode} from 'react';
import {Button, Empty, Modal, Space, Spin, Typography} from 'antd';
import type {ReleaseChangeLogData, ReleaseNote} from '../hooks/useReleaseChangeLog';

function ReleaseList({releases}: {releases: ReleaseNote[]}) {
  if (!releases.length) return <Empty description="Записей о релизах пока нет"/>;
  return <div style={{maxHeight: '60vh', overflowY: 'auto'}}>
    {releases.map((release) => <section key={release.version} style={{marginBottom: 20}}>
      <Space size={8} wrap>
        <Typography.Text type="secondary">{release.date}</Typography.Text>
        <Typography.Text strong>v{release.version}</Typography.Text>
      </Space>
      <Typography.Title level={5} style={{margin: '6px 0'}}>{release.title}</Typography.Title>
      <ul style={{margin: 0, paddingLeft: 20}}>
        {release.changes.map((change) => <li key={change} style={{padding: '2px 0'}}>{change}</li>)}
      </ul>
    </section>)}
  </div>;
}

function ReleaseChangeLogDialog({
  open,
  title,
  releases,
  loading,
  acknowledging,
  onClose,
  onAcknowledge,
}: {
  open: boolean;
  title: string;
  releases: ReleaseNote[];
  loading?: boolean;
  acknowledging?: boolean;
  onClose: () => void;
  onAcknowledge?: () => void;
}) {
  return <Modal
    open={open}
    title={title}
    onCancel={onClose}
    closable={!acknowledging}
    keyboard={!acknowledging}
    mask={{closable: !acknowledging}}
    footer={onAcknowledge ? <Button type="primary" loading={acknowledging} onClick={onAcknowledge}>Понятно</Button> :
      <Button onClick={onClose}>Закрыть</Button>}
  >
    {loading ? <div style={{textAlign: 'center', padding: 24}}><Spin/></div> :
      <ReleaseList releases={releases}/>}
  </Modal>;
}

export interface ReleaseChangeLogShellState {
  application?: ReleaseChangeLogData['application'];
  openHistory: () => void;
}

export function ReleaseChangeLogExperience({
  data,
  isLoading,
  isAcknowledging,
  markSeen,
  children,
}: {
  data?: ReleaseChangeLogData;
  isLoading: boolean;
  isAcknowledging: boolean;
  markSeen: (versions: string[]) => Promise<unknown>;
  children: (state: ReleaseChangeLogShellState) => ReactNode;
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [announcementOpen, setAnnouncementOpen] = useState(false);
  const handledInitialData = useRef(false);

  useEffect(() => {
    if (!data || handledInitialData.current) return;
    handledInitialData.current = true;
    if (data.unseen_releases.length) setAnnouncementOpen(true);
  }, [data]);

  async function acknowledgeAnnouncement() {
    if (!data?.unseen_releases.length || isAcknowledging) return;
    try {
      await markSeen(data.unseen_releases.map((release) => release.version));
      setAnnouncementOpen(false);
    } catch {
      // Keep the summary open so the user can retry; the mutation reports the error.
    }
  }

  return <>
    {children({application: data?.application, openHistory: () => setHistoryOpen(true)})}
    <ReleaseChangeLogDialog
      open={historyOpen}
      title="История изменений"
      releases={data?.releases ?? []}
      loading={isLoading}
      onClose={() => setHistoryOpen(false)}
    />
    <ReleaseChangeLogDialog
      open={announcementOpen}
      title="Что нового"
      releases={data?.unseen_releases ?? []}
      acknowledging={isAcknowledging}
      onClose={acknowledgeAnnouncement}
      onAcknowledge={acknowledgeAnnouncement}
    />
  </>;
}
