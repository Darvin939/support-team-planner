import {useEffect, useState} from 'react';
import {useParams} from 'react-router-dom';
import type {TableColumnsType} from 'antd';
import {Card, DatePicker, Empty, Input, Modal, Select, Table, Tag, Tooltip, Typography} from 'antd';
import dayjs from 'dayjs';
import {useTeams} from '../hooks/useTeams';
import {useUserNames, useUserOptions} from '../hooks/useUserNames';
import {useIsMobile} from '../hooks/useIsMobile';
import {useDateRangeFilter} from '../hooks/useDateRangeFilter';
import {FilterField, FilterGrid} from '../components/FilterGrid';
import {formatChangedBy, formatHistoryText, groupHistoryEntries, type HistoryEntry, type HistoryEvent} from '../lib/historyFormat';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {useDebouncedValue} from '../hooks/useDebouncedValue';
import {useStoredTeamRoute} from '../hooks/useStoredTeamRoute';
import {usePaginationState} from '../hooks/usePaginationState';
import {JOURNAL_PAGE_SIZE, type JournalFilters, useJournal} from '../hooks/useJournalData';
import {getHistoryEventColor, getHistoryEventKind, getHistoryEventSummary, HISTORY_PAGE_SIZE, HistoryEntries, useEntityHistory} from './planning/historyShared';
import {AppPagination} from '../components/AppPagination';
import {TOP_BAR_HEIGHT} from '../components/AppShell';

export function buildJournalColumns(_getUserName: (id: string) => string): TableColumnsType<HistoryEvent> {
  return [
    {
      title: 'Дата и время',
      key: 'changed_at',
      width: 170,
      render: (_, event) => event.entries[0].changed_at,
    },
    {
      title: 'Работа',
      key: 'task_name',
      width: 260,
      ellipsis: {showTitle: false},
      render: (_: string | undefined, event) => {
        const item = event.entries[0];
        const taskName = item.task_name;
        return (
        <Tooltip title={taskName || '—'}>
          <span>
            {taskName || '—'}
            {item.task_is_deleted ? <Tag style={{marginLeft: 6}}>удалена</Tag> : null}
          </span>
        </Tooltip>
        );
      },
    },
    {
      title: 'Объект',
      key: 'entity',
      width: 130,
      responsive: ['lg'],
      render: (_, event) => <Tag>{event.entries[0].entity === 'assignment' ? 'Назначение' : 'Работа'}</Tag>,
    },
    {
      title: 'Изменение',
      key: 'change',
      width: 180,
      render: (_, event) => <Tag color={getHistoryEventColor(getHistoryEventKind(event))}>{getHistoryEventSummary(event)}</Tag>,
    },
    {
      title: 'Автор',
      key: 'author',
      width: 180,
      render: (_, event) => formatChangedBy(event.entries[0]),
    },
  ];
}

export function buildTaskHistoryColumns(getUserName: (id: string) => string): TableColumnsType<HistoryEntry> {
  return [
    {title: 'Дата и время', dataIndex: 'changed_at', key: 'changed_at', width: 170},
    {
      title: 'Изменение',
      key: 'change',
      width: 520,
      render: (_, entry) => formatHistoryText(entry, getUserName, false),
    },
    {title: 'Автор', key: 'author', width: 180, render: (_, entry) => formatChangedBy(entry)},
  ];
}

function TaskHistoryModal({kind, entityId, taskName, date, onClose}: {
  kind: 'task' | 'assignment' | null;
  entityId: number | null;
  taskName: string | null;
  date: string | null;
  onClose: () => void
}) {
  const pagination = usePaginationState(HISTORY_PAGE_SIZE);
  const {data, isLoading} = useEntityHistory(kind ?? 'task', entityId, pagination.offset);

  useEffect(() => {
    if (entityId !== null) pagination.reset();
  }, [entityId, kind, pagination.reset]);

  const title = kind === 'assignment'
    ? `История назначения: ${taskName || 'Работа'}${date ? ` · ${date}` : ''}`
    : taskName ? `История работы: ${taskName}` : 'История работы';

  return (
    <Modal title={title} open={entityId !== null} onCancel={onClose} footer={null} width={900} destroyOnHidden>
      <HistoryEntries entries={data?.history} loading={isLoading} showAssignmentContext={kind === 'task'}/>
      {data && <AppPagination compact current={pagination.page} pageSize={pagination.pageSize}
                              total={data.total} onChange={pagination.onChange}/>}
    </Modal>
  );
}

export function JournalPage() {
  const {teamId: teamIdParam} = useParams();
  const isMobile = useIsMobile();
  const {data: teams} = useTeams();
  const userOptions = useUserOptions();
  const pagination = usePaginationState(JOURNAL_PAGE_SIZE);
  const [modalHistory, setModalHistory] = useState<{
    kind: 'task' | 'assignment'; id: number; taskName: string; date: string | null
  } | null>(null);
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

  const {data, isLoading} = useJournal(teamId, pagination.offset, pagination.pageSize, filters);
  const columns = buildJournalColumns(getUserName);
  const events = groupHistoryEntries(data?.items ?? []);

  function handleTeamSelect(value: number | undefined) {
    selectTeamRoute(value);
  }

  return (
    <>
      <Typography.Title level={2}>Журнал изменений</Typography.Title>

      <Card style={{marginBottom: 16}}>
        <Select
          style={{minWidth: 300}}
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

          <Table<HistoryEvent>
            rowKey={(event) => event.key}
            columns={columns}
            dataSource={events}
            loading={isLoading}
            pagination={false}
            size="small"
            scroll={{x: 1160}}
            sticky={{offsetHeader: isMobile ? TOP_BAR_HEIGHT : 0}}
            locale={{emptyText: 'Изменений пока нет'}}
            onRow={(event) => ({
              onClick: () => {
                const item = event.entries[0];
                const kind = item.entity === 'assignment' && item.assignment_id ? 'assignment' : 'task';
                const id = kind === 'assignment' ? item.assignment_id : item.task_id;
                if (id == null) return;
                setModalHistory({kind, id, taskName: item.task_name ?? '', date: item.date ?? null});
              },
              style: {cursor: 'pointer'},
            })}
            style={{marginBottom: 16}}
          />
          {data && <AppPagination current={pagination.page} pageSize={pagination.pageSize} total={data.total}
                                  allowPageSizeChange onChange={pagination.onChange}/>}
        </>
      )}

      <TaskHistoryModal kind={modalHistory?.kind ?? null} entityId={modalHistory?.id ?? null}
                        taskName={modalHistory?.taskName ?? null} date={modalHistory?.date ?? null}
                        onClose={() => setModalHistory(null)}/>
    </>
  );
}
