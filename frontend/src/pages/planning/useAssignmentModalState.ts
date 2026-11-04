import {useEffect, useState} from 'react';
import {Form, type FormInstance} from 'antd';
import dayjs from 'dayjs';
import type {Assignment, BlockTemplateWithBlocks, TeamBlock} from '../../hooks/usePlanningData';
import {computeAutoAssignDates} from '../../lib/autoSchedule';
import {API_DATE_FORMAT, TIME_FORMAT} from '../../lib/dateFormats';
import type {AssignmentFormValues} from './AssignmentModal';

export function useAssignmentModalState({
                                          open, taskId, assignment, date, teamBlocks, template, freezeDays, form,
                                        }: {
  open: boolean;
  taskId: number | undefined;
  assignment: Assignment | null;
  date: string | null;
  teamBlocks: TeamBlock[] | undefined;
  template: BlockTemplateWithBlocks | undefined;
  freezeDays: Set<string>;
  form: FormInstance<AssignmentFormValues>;
}) {
  const [autoAssignEnabled, setAutoAssignEnabled] = useState(false);
  const [autoAssignDates, setAutoAssignDates] = useState<Record<number, string>>({});
  const [autoAssignSelected, setAutoAssignSelected] = useState<number | null>(null);
  const watchedDate = Form.useWatch('date', form);

  useEffect(() => {
    if (!open) return;
    const names = (assignment?.block ?? '').split(',').map((value) => value.trim()).filter(Boolean);
    const blockIds = (teamBlocks ?? []).filter((block) => names.includes(block.name)).map((block) => block.id);
    form.setFieldsValue({
      date: dayjs(assignment?.date ?? date ?? undefined),
      time_spent: assignment?.time_spent ? dayjs(assignment.time_spent, TIME_FORMAT) : null,
      block_ids: blockIds,
      status: assignment?.status ?? 'new',
      user_id: assignment?.user_id ?? null,
      comment: assignment?.comment ?? '',
    });
    setAutoAssignEnabled(false);
    setAutoAssignDates({});
    setAutoAssignSelected(null);
  }, [open, taskId, assignment, date, teamBlocks, form]);

  useEffect(() => {
    if (!autoAssignEnabled || !watchedDate) return;
    setAutoAssignDates(template ? computeAutoAssignDates(
      watchedDate.format(API_DATE_FORMAT), template.blocks, freezeDays,
    ) : {});
    setAutoAssignSelected(null);
  }, [watchedDate, autoAssignEnabled, template, freezeDays]);

  function handleAutoAssignToggle(checked: boolean) {
    setAutoAssignEnabled(checked);
    setAutoAssignSelected(null);
    if (!checked) return;
    form.setFieldValue('status', 'new');
  }

  return {
    autoAssignEnabled, autoAssignDates, autoAssignSelected, watchedDate,
    setAutoAssignDates, setAutoAssignSelected, handleAutoAssignToggle,
  };
}
