import {useEffect, useState} from 'react';
import {useParams} from 'react-router-dom';
import {Card, DatePicker, Empty, Input, Modal, Select, Tag, Typography} from 'antd';
import {useQuery} from '@tanstack/react-query';
import dayjs from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useUserNames, useUserOptions} from '../hooks/useUserNames';
import {useIsMobile} from '../hooks/useIsMobile';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {formatChangedBy, formatHistoryText, type HistoryEntry} from '../lib/historyFormat';
import {apiGet} from '../lib/apiMutate';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {useDebouncedValue} from '../hooks/useDebouncedValue';
import {useStoredTeamRoute} from '../hooks/useStoredTeamRoute';
import {queryKeys} from '../lib/queryKeys';
import {usePaginationState} from '../hooks/usePaginationState';
import {HISTORY_PAGE_SIZE, HistoryEntries, useEntityHistory} from './planning/historyShared';
import {OffsetPagination} from '../components/OffsetPagination';

const JOURNAL_PAGE_SIZE = 20;

interface JournalItem extends HistoryEntry {
  task_id: number;
}

interface JournalFilters {
  search: string;
  dateFrom: string | null;
  dateTo: string | null;
  changedByUserId: number | null;
}

function useJournal(teamId: number | undefined, offset: number, filters: JournalFilters) {
  return useQuery<{ items: JournalItem[]; total: number }>({
    queryKey: queryKeys.journal(teamId, offset, filters),
    enabled: teamId !== undefined,
    queryFn: () => {
      const params = new URLSearchParams({offset: String(offset), limit: String(JOURNAL_PAGE_SIZE)});
      if (filters.search) params.set('search', filters.search);
      if (filters.dateFrom) params.set('date_from', filters.dateFrom);
      if (filters.dateTo) params.set('date_to', filters.dateTo);
      if (filters.changedByUserId) params.set('changed_by_user_id', String(filters.changedByUserId));
      return apiGet(`/api/journal/${teamId}?${params}`);
    },
  });
}

function TaskHistoryModal({taskId, taskName, onClose}: {
  taskId: number | null;
  taskName: string | null;
  onClose: () => void
}) {
  const pagination = usePaginationState(HISTORY_PAGE_SIZE);
  const {data, isLoading} = useEntityHistory('task', taskId, pagination.offset);

  useEffect(() => {
    if (taskId !== null) pagination.reset();
  }, [taskId, pagination.reset]);

  return (
    <Modal title={taskName ? `История задачи: ${taskName}` : 'История задачи'} open={taskId !== null} onCancel={onClose}
           footer={null} width={700}>
      <HistoryEntries entries={data?.history} loading={isLoading} showAssignmentContext={false}/>
      {data && <OffsetPagination style={{marginTop: 12, textAlign: 'center'}} offset={pagination.offset}
                                 pageSize={HISTORY_PAGE_SIZE} total={data.total}
                                 onOffsetChange={pagination.setOffset}/>}
    </Modal>
  );
}

export function JournalPage() {
  const {teamId: teamIdParam} = useParams();
  const isMobile = useIsMobile();
  const {data: teams} = useTeams();
  const userOptions = useUserOptions();
  const pagination = usePaginationState(JOURNAL_PAGE_SIZE);
  const [modalTask, setModalTask] = useState<{ id: number; name: string } | null>(null);
  const getUserName = useUserNames();

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 500);
  const [dateRange, handleDateRangeChange] = useDateRangeFilter(null, {
    storageKeyFrom: 'journalDateFrom',
    storageKeyTo: 'journalDateTo',
    maxPeriodDays: Infinity,
    onChange: pagination.reset,
  });
  const [changedByUserId, setChangedByUserId] = useState<number | null>(null);

  const teamId = teamIdParam ? Number(teamIdParam) : undefined;
  const selectTeamRoute = useStoredTeamRoute('/journal', teamId, teams);

  useEffect(() => {
    pagination.reset();
  }, [teamId, pagination.reset]);

  useEffect(() => {
    pagination.reset();
  }, [debouncedSearch, pagination.reset]);

  function handleChangedByChange(value: number | undefined) {
    setChangedByUserId(value ?? null);
    pagination.reset();
  }

  const filters: JournalFilters = {
    search: debouncedSearch,
    dateFrom: dateRange ? dateRange[0].format(API_DATE_FORMAT) : null,
    dateTo: dateRange ? dateRange[1].format(API_DATE_FORMAT) : null,
    changedByUserId,
  };

  const {data} = useJournal(teamId, pagination.offset, filters);

  function handleTeamSelect(value: number | undefined) {
    selectTeamRoute(value);
  }

  return (
    <>
      <Typography.Title level={2}>Журнал изменений</Typography.Title>

      <Card style={{marginBottom: 16}}>
        <Select
          style={{minWidth: 260}}
          placeholder="-- Выберите команду --"
          value={teamId}
          onChange={handleTeamSelect}
          allowClear
          showSearch={{optionFilterProp: 'label'}}
          options={teams?.map((t) => ({value: t.id, label: t.name}))}
        />
      </Card>

      {teamId === undefined ? (
        <Empty description="Выберите команду, чтобы посмотреть журнал изменений"/>
      ) : (
        <>
          <Card style={{marginBottom: 16}}>
            <Typography.Title level={5} style={{marginTop: 0}}>
              Фильтры
            </Typography.Title>
            <FilterGrid isMobile={isMobile}>
              <FilterField label="ПЕРИОД" isMobile={isMobile} mobileSpan={2}>
                <DatePicker.RangePicker
                  value={dateRange}
                  onChange={handleDateRangeChange}
                  format={DISPLAY_DATE_FORMAT}
                  minDate={dayjs('2000-01-01')}
                  maxDate={dayjs('2099-12-31')}
                  allowClear
                  style={isMobile ? {width: '100%'} : undefined}
                />
              </FilterField>
              <FilterField label="ПОИСК ПО РАБОТЕ" isMobile={isMobile}>
                <Input.Search
                  style={{width: isMobile ? '100%' : 220}}
                  placeholder="Введите текст..."
                  allowClear
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </FilterField>
              <FilterField label="АВТОР ИЗМЕНЕНИЯ" isMobile={isMobile}>
                <Select
                  style={{width: isMobile ? '100%' : 220}}
                  placeholder="Все"
                  allowClear
                  showSearch={{optionFilterProp: "label"}}
                  value={changedByUserId ?? undefined}
                  onChange={handleChangedByChange}
                  options={userOptions}
                />
              </FilterField>
            </FilterGrid>
          </Card>

          {data && data.items.length === 0 && <Empty description="Изменений пока нет"/>}
          <div style={{display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16}}>
            {data?.items.map((item) => (
              <Card
                key={`${item.entity}-${item.id}`}
                size="small"
                hoverable
                onClick={() => setModalTask({id: item.task_id, name: item.task_name ?? ''})}
                styles={{body: {fontSize: '0.9rem'}}}
              >
                <div style={{opacity: 0.6, fontSize: '0.8rem'}}>
                  {item.changed_at} — {formatChangedBy(item)}
                </div>
                <div>
                  «{item.task_name}»{item.task_is_deleted ? <Tag style={{marginLeft: 6}}>удалена</Tag> : null} —{' '}
                  {formatHistoryText(item, getUserName, true)}
                </div>
              </Card>
            ))}
          </div>
          {data && <OffsetPagination style={{textAlign: 'center'}} offset={pagination.offset}
                                     pageSize={JOURNAL_PAGE_SIZE} total={data.total}
                                     onOffsetChange={pagination.setOffset} simple={false}/>}
        </>
      )}

      <TaskHistoryModal taskId={modalTask?.id ?? null} taskName={modalTask?.name ?? null}
                        onClose={() => setModalTask(null)}/>
    </>
  );
}
