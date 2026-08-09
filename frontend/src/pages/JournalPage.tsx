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
import {formatChangedBy, formatHistoryText, type HistoryEntry} from '../lib/historyFormat';
import {API_DATE_FORMAT, DISPLAY_DATE_FORMAT} from '../lib/dateFormats';
import {useDebouncedValue} from '../hooks/useDebouncedValue';
import {useStoredTeamRoute} from '../hooks/useStoredTeamRoute';
import {usePaginationState} from '../hooks/usePaginationState';
import {JOURNAL_PAGE_SIZE, type JournalFilters, type JournalItem, useJournal} from '../hooks/useJournalData';
import {HISTORY_PAGE_SIZE, useEntityHistory} from './planning/historyShared';
import {OffsetPagination} from '../components/OffsetPagination';
import {PagePagination} from '../components/PagePagination';
import {TOP_BAR_HEIGHT} from '../components/AppShell';

export function buildJournalColumns(getUserName: (id: string) => string): TableColumnsType<JournalItem> {
  return [
    {
      title: 'Дата и время',
      dataIndex: 'changed_at',
      key: 'changed_at',
      width: 170,
    },
    {
      title: 'Работа',
      dataIndex: 'task_name',
      key: 'task_name',
      width: 260,
      ellipsis: {showTitle: false},
      render: (taskName: string | undefined, item) => (
        <Tooltip title={taskName || '—'}>
          <span>
            {taskName || '—'}
            {item.task_is_deleted ? <Tag style={{marginLeft: 6}}>удалена</Tag> : null}
          </span>
        </Tooltip>
      ),
    },
    {
      title: 'Объект',
      dataIndex: 'entity',
      key: 'entity',
      width: 130,
      responsive: ['lg'],
      render: (entity: JournalItem['entity']) => (
        <Tag>{entity === 'assignment' ? 'Назначение' : 'Работа'}</Tag>
      ),
    },
    {
      title: 'Изменение',
      key: 'change',
      width: 420,
      ellipsis: {showTitle: false},
      render: (_, item) => {
        const text = formatHistoryText(item, getUserName, true);
        return <Tooltip title={text}><span>{text}</span></Tooltip>;
      },
    },
    {
      title: 'Автор',
      key: 'author',
      width: 180,
      render: (_, item) => formatChangedBy(item),
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

function TaskHistoryModal({taskId, taskName, onClose}: {
  taskId: number | null;
  taskName: string | null;
  onClose: () => void
}) {
  const pagination = usePaginationState(HISTORY_PAGE_SIZE);
  const {data, isLoading} = useEntityHistory('task', taskId, pagination.offset);
  const getUserName = useUserNames();

  useEffect(() => {
    if (taskId !== null) pagination.reset();
  }, [taskId, pagination.reset]);

  return (
    <Modal title={taskName ? `История задачи: ${taskName}` : 'История задачи'} open={taskId !== null} onCancel={onClose}
           footer={null} width={1000} destroyOnHidden>
      <Table<HistoryEntry>
        rowKey={(entry) => `${entry.entity ?? 'entity'}-${entry.id}`}
        size="small"
        loading={isLoading}
        dataSource={data?.history ?? []}
        pagination={false}
        columns={buildTaskHistoryColumns(getUserName)}
        locale={{emptyText: 'Изменений пока нет'}}
        scroll={{x: 870}}
      />
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

  const {data, isLoading} = useJournal(teamId, pagination.offset, pagination.pageSize, filters);
  const columns = buildJournalColumns(getUserName);

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

          <Table<JournalItem>
            rowKey={(item) => `${item.entity ?? 'entity'}-${item.id}`}
            columns={columns}
            dataSource={data?.items ?? []}
            loading={isLoading}
            pagination={false}
            size="small"
            scroll={{x: 1160}}
            sticky={{offsetHeader: isMobile ? TOP_BAR_HEIGHT : 0}}
            locale={{emptyText: 'Изменений пока нет'}}
            onRow={(item) => ({
              onClick: () => setModalTask({id: item.task_id, name: item.task_name ?? ''}),
              style: {cursor: 'pointer'},
            })}
            style={{marginBottom: 16}}
          />
          {data && <PagePagination current={pagination.page} pageSize={pagination.pageSize} total={data.total}
                                   onChange={pagination.onChange}/>}
        </>
      )}

      <TaskHistoryModal taskId={modalTask?.id ?? null} taskName={modalTask?.name ?? null}
                        onClose={() => setModalTask(null)}/>
    </>
  );
}
