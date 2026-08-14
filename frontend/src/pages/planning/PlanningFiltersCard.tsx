import type {Dispatch, SetStateAction} from 'react';
import {Card, Checkbox, DatePicker, Input, Select, Typography} from 'antd';
import dayjs, {type Dayjs} from 'dayjs';
import {FilterField, FilterGrid} from '../../components/FilterGrid';
import {ASSIGNMENT_STATUS_OPTIONS, CRITICALITY_OPTIONS, TASK_STATUS_OPTIONS, type AssignmentStatus, type Criticality, type Segment, type TaskStatus} from '../../domain/types';
import {DISPLAY_DATE_FORMAT} from '../../lib/dateFormats';

export function PlanningFiltersCard(props: {
  isMobile: boolean;
  range: [Dayjs, Dayjs];
  onRangeChange: (dates: [Dayjs | null, Dayjs | null] | null) => void;
  search: string;
  setSearch: Dispatch<SetStateAction<string>>;
  criticalities: Criticality[];
  setCriticalities: Dispatch<SetStateAction<Criticality[]>>;
  segmentIds: number[];
  setSegmentIds: Dispatch<SetStateAction<number[]>>;
  assignmentStatuses: AssignmentStatus[];
  setAssignmentStatuses: Dispatch<SetStateAction<AssignmentStatus[]>>;
  taskStatuses: TaskStatus[];
  setTaskStatuses: Dispatch<SetStateAction<TaskStatus[]>>;
  segments: Segment[] | undefined;
  showCompleted: boolean;
  setShowCompleted: Dispatch<SetStateAction<boolean>>;
}) {
  const width = props.isMobile ? '100%' : 180;
  return (
    <Card style={{marginBottom: 16}}>
      <Typography.Title level={5} style={{marginTop: 0}}>Фильтры</Typography.Title>
      <FilterGrid isMobile={props.isMobile}>
        <FilterField label="ПЕРИОД" isMobile={props.isMobile} mobileSpan={2}>
          <DatePicker.RangePicker value={props.range} onChange={props.onRangeChange}
            format={DISPLAY_DATE_FORMAT} minDate={dayjs('2000-01-01')} maxDate={dayjs('2099-12-31')}
            allowClear style={props.isMobile ? {width: '100%'} : undefined}/>
        </FilterField>
        <FilterField label="ПОИСК ПО ОПИСАНИЮ" isMobile={props.isMobile}>
          <Input.Search style={{width: props.isMobile ? '100%' : 220}} placeholder="Введите текст..."
            allowClear value={props.search} onChange={(event) => props.setSearch(event.target.value)}/>
        </FilterField>
        <FilterField label="КРИТИЧНОСТЬ" isMobile={props.isMobile}>
          <Select mode="multiple" style={{width}} placeholder="Все" value={props.criticalities}
            onChange={props.setCriticalities} options={CRITICALITY_OPTIONS}/>
        </FilterField>
        <FilterField label="СЕГМЕНТ" isMobile={props.isMobile}>
          <Select mode="multiple" style={{width}} placeholder="Все" value={props.segmentIds}
            onChange={props.setSegmentIds}
            options={props.segments?.map((segment) => ({value: segment.id, label: segment.name}))}/>
        </FilterField>
        <FilterField label="СТАТУС" isMobile={props.isMobile}>
          <Select mode="multiple" style={{width}} placeholder="Все" value={props.assignmentStatuses}
            onChange={props.setAssignmentStatuses} options={ASSIGNMENT_STATUS_OPTIONS}/>
        </FilterField>
        <FilterField label="СТАТУС РАБОТЫ" isMobile={props.isMobile}>
          <Select mode="multiple" style={{width}} placeholder="Все" value={props.taskStatuses}
            onChange={props.setTaskStatuses} options={TASK_STATUS_OPTIONS}/>
        </FilterField>
        <FilterField isMobile={props.isMobile} mobileSpan="full">
          <div style={{display: 'flex', alignItems: 'center', height: '100%'}}>
            <Checkbox checked={props.showCompleted}
              onChange={(event) => props.setShowCompleted(event.target.checked)}>
              Завершённые за 30 дней
            </Checkbox>
          </div>
        </FilterField>
      </FilterGrid>
    </Card>
  );
}
