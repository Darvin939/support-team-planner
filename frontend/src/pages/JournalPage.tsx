import {useEffect, useState} from 'react';
import {useNavigate, useParams} from 'react-router-dom';
import {Card, Empty, Modal, Pagination, Select, Spin, Tag, Typography} from 'antd';
import {useQuery} from '@tanstack/react-query';
import {useTeams} from '../hooks/useTeams';
import {useEmployeeNames} from '../hooks/useEmployeeNames';
import {formatChangedBy, formatHistoryText, type HistoryEntry} from '../lib/historyFormat';

const JOURNAL_PAGE_SIZE = 20;
const HISTORY_PAGE_SIZE = 10;
const STORAGE_TEAM_ID = 'selectedTeamId';

interface JournalItem extends HistoryEntry {
  task_id: number;
}

function useJournal(teamId: number | undefined, offset: number) {
  return useQuery<{ items: JournalItem[]; total: number }>({
    queryKey: ['journal', teamId, offset],
    enabled: teamId !== undefined,
    queryFn: async () => {
      const r = await fetch(`/api/journal/${teamId}?offset=${offset}&limit=${JOURNAL_PAGE_SIZE}`, { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/journal -> ${r.status}`);
      return r.json();
    },
  });
}

function useTaskHistory(taskId: number | null, offset: number) {
  return useQuery<{ history: HistoryEntry[]; total: number }>({
    queryKey: ['task-history', taskId, offset],
    enabled: taskId !== null,
    queryFn: async () => {
      const r = await fetch(`/api/task/${taskId}/history?offset=${offset}&limit=${HISTORY_PAGE_SIZE}`, { credentials: 'same-origin' });
      if (!r.ok) throw new Error(`GET /api/task/history -> ${r.status}`);
      return r.json();
    },
  });
}

function TaskHistoryModal({ taskId, taskName, onClose }: { taskId: number | null; taskName: string | null; onClose: () => void }) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useTaskHistory(taskId, offset);
  const getEmployeeName = useEmployeeNames();

  useEffect(() => {
    if (taskId !== null) setOffset(0);
  }, [taskId]);

  return (
    <Modal title={taskName ? `История задачи: ${taskName}` : 'История задачи'} open={taskId !== null} onCancel={onClose} footer={null} width={700}>
      {isLoading && <Spin />}
      {data && data.history.length === 0 && <Empty description="Изменений пока нет" />}
      {data && data.history.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.history.map((entry) => (
            <div key={entry.id} style={{ fontSize: '0.85rem', padding: '6px 10px', background: 'rgba(128,128,128,0.08)', borderRadius: 4 }}>
              <div style={{ opacity: 0.6, fontSize: '0.78rem' }}>
                {entry.changed_at} — {formatChangedBy(entry)}
              </div>
              <div>{formatHistoryText(entry, getEmployeeName, false)}</div>
            </div>
          ))}
        </div>
      )}
      {data && data.total > HISTORY_PAGE_SIZE && (
        <Pagination
          style={{ marginTop: 12, textAlign: 'center' }}
          simple
          showSizeChanger={false}
          current={Math.floor(offset / HISTORY_PAGE_SIZE) + 1}
          pageSize={HISTORY_PAGE_SIZE}
          total={data.total}
          onChange={(page) => setOffset((page - 1) * HISTORY_PAGE_SIZE)}
        />
      )}
    </Modal>
  );
}

export function JournalPage() {
  const { teamId: teamIdParam } = useParams();
  const navigate = useNavigate();
  const { data: teams } = useTeams();
  const [offset, setOffset] = useState(0);
  const [modalTask, setModalTask] = useState<{ id: number; name: string } | null>(null);
  const getEmployeeName = useEmployeeNames();

  const teamId = teamIdParam ? Number(teamIdParam) : undefined;

  useEffect(() => {
    if (teamId !== undefined) return;
    const saved = localStorage.getItem(STORAGE_TEAM_ID);
    if (saved && saved !== '0') navigate(`/journal/${saved}`, { replace: true });
  }, [teamId, navigate]);

  useEffect(() => {
    setOffset(0);
  }, [teamId]);

  const { data } = useJournal(teamId, offset);

  function handleTeamSelect(value: number | undefined) {
    localStorage.setItem(STORAGE_TEAM_ID, value ? String(value) : '');
    navigate(value ? `/journal/${value}` : '/journal');
  }

  return (
    <>
      <Typography.Title level={2}>Журнал изменений</Typography.Title>

      <Card style={{ marginBottom: 16 }}>
        <Select
          style={{ minWidth: 260 }}
          placeholder="-- Выберите команду --"
          value={teamId}
          onChange={handleTeamSelect}
          allowClear
          options={teams?.map((t) => ({ value: t.id, label: t.name }))}
        />
      </Card>

      {teamId === undefined ? (
        <Empty description="Выберите команду, чтобы посмотреть журнал изменений" />
      ) : (
        <>
          {data && data.items.length === 0 && <Empty description="Изменений пока нет" />}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {data?.items.map((item) => (
              <Card
                key={item.id}
                size="small"
                hoverable
                onClick={() => setModalTask({ id: item.task_id, name: item.task_name ?? '' })}
                styles={{ body: { fontSize: '0.9rem' } }}
              >
                <div style={{ opacity: 0.6, fontSize: '0.8rem' }}>
                  {item.changed_at} — {formatChangedBy(item)}
                </div>
                <div>
                  «{item.task_name}»{item.task_is_deleted ? <Tag style={{ marginLeft: 6 }}>удалена</Tag> : null} —{' '}
                  {formatHistoryText(item, getEmployeeName, true)}
                </div>
              </Card>
            ))}
          </div>
          {data && data.total > JOURNAL_PAGE_SIZE && (
            <Pagination
              style={{ textAlign: 'center' }}
              current={Math.floor(offset / JOURNAL_PAGE_SIZE) + 1}
              pageSize={JOURNAL_PAGE_SIZE}
              total={data.total}
              onChange={(page) => setOffset((page - 1) * JOURNAL_PAGE_SIZE)}
              showSizeChanger={false}
            />
          )}
        </>
      )}

      <TaskHistoryModal taskId={modalTask?.id ?? null} taskName={modalTask?.name ?? null} onClose={() => setModalTask(null)} />
    </>
  );
}
