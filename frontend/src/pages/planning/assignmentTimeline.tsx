import dayjs from 'dayjs';
import {Alert, Spin, theme} from 'antd';
import {ASSIGNMENT_STATUS_LABELS, type AssignmentStatus} from '../../domain/types';
import {DISPLAY_DATE_SHORT_FORMAT} from '../../lib/dateFormats';
import type {AssignmentTimelineItem} from '../../hooks/usePlanningData';
import {buildAssignmentTimelineDates, splitAssignmentBlocks} from './assignmentTimelineUtils';
import {PlanningDateGrid} from './PlanningDateGrid';

function statusColor(token: ReturnType<typeof theme.useToken>['token'], status: AssignmentStatus): string {
  return status === 'planned' ? token.colorWarning
    : status === 'rollback' ? token.colorError
      : status === 'success' ? token.colorSuccess
        : status === 'cancelled' ? token.colorTextSecondary : token.colorPrimary;
}

export function AssignmentTimeline({assignments, loading = false, error = false}: {
  assignments: AssignmentTimelineItem[] | undefined;
  loading?: boolean;
  error?: boolean;
}) {
  const {token} = theme.useToken();
  if (loading) return <div data-assignment-timeline><Spin size="small"/></div>;
  if (error) return <div data-assignment-timeline><Alert type="error" showIcon message="Не удалось загрузить назначения"/></div>;
  if (!assignments || assignments.length === 0) {
    return <div data-assignment-timeline><span style={{color: token.colorTextTertiary}}>Назначений нет</span></div>;
  }

  const dates = buildAssignmentTimelineDates(assignments);
  const byDate = new Map<string, AssignmentTimelineItem[]>();
  for (const assignment of assignments) {
    const values = byDate.get(assignment.date) ?? [];
    values.push(assignment);
    byDate.set(assignment.date, values);
  }

  return (
    <div data-assignment-timeline>
      <PlanningDateGrid
        dates={dates}
        firstColumnHeader="Дата"
        firstColumnBody="Блок"
        fontSize={token.fontSizeSM}
        dataAttribute="data-assignment-timeline"
        renderDateHeader={(date) => dayjs(date).format(DISPLAY_DATE_SHORT_FORMAT)}
        getDateHeaderStyle={() => ({minWidth: 104})}
        renderDateCell={(date) => {
          const entries = byDate.get(date) ?? [];
          const status = entries[0]?.status;
          if (!status) return null;
          const blocks = entries.flatMap((assignment) => splitAssignmentBlocks(assignment.block));
          const color = statusColor(token, status);
          return (
            <span style={{display: 'inline-block', minWidth: 104, borderLeft: `3px solid ${color}`, padding: '2px 6px', background: token.colorFillTertiary, borderRadius: token.borderRadiusSM}}>
              <span style={{fontWeight: 600}}>{blocks.join(', ') || '—'}</span>{' '}
              <span style={{display: 'block', fontSize: token.fontSizeSM, color}}>{ASSIGNMENT_STATUS_LABELS[status] ?? status}</span>
            </span>
          );
        }}
      />
    </div>
  );
}
