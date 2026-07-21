import {useEffect, useState} from 'react';
import {Form, type FormInstance} from 'antd';
import dayjs from 'dayjs';
import type {Assignment, BlockTemplateWithBlocks, TeamBlock} from '../../hooks/usePlanningData';
import {computeAutoAssignDates} from '../../lib/autoSchedule';
import {API_DATE_FORMAT, TIME_FORMAT} from '../../lib/dateFormats';
import type {AssignmentFormValues} from './AssignmentModal';

export function useAssignmentModalState({
                                          open, assignment, date, teamBlocks, templates, freezeDays, form,
                                        }: {
  open: boolean;
  assignment: Assignment | null;
  date: string | null;
  teamBlocks: TeamBlock[] | undefined;
  templates: BlockTemplateWithBlocks[] | undefined;
  freezeDays: Set<string>;
  form: FormInstance<AssignmentFormValues>;
}) {
  const [autoAssignEnabled, setAutoAssignEnabled] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
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
    setSelectedTemplateId(null);
    setAutoAssignDates({});
    setAutoAssignSelected(null);
  }, [open, assignment, date, teamBlocks, form]);

  function recomputeSchedule(templateId: number | null, baseDate: string) {
    const blocks = templates?.find((template) => template.id === templateId)?.blocks ?? [];
    setAutoAssignDates(templateId ? computeAutoAssignDates(baseDate, blocks, freezeDays) : {});
  }

  useEffect(() => {
    if (!autoAssignEnabled || !watchedDate) return;
    recomputeSchedule(selectedTemplateId, watchedDate.format(API_DATE_FORMAT));
    // recomputeSchedule intentionally follows the same form-driven lifecycle as before extraction.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [watchedDate, autoAssignEnabled, selectedTemplateId, templates]);

  function handleAutoAssignToggle(checked: boolean) {
    setAutoAssignEnabled(checked);
    setAutoAssignSelected(null);
    if (!checked) return;
    form.setFieldValue('status', 'new');
    const defaultTemplateId = templates?.[0]?.id ?? null;
    setSelectedTemplateId(defaultTemplateId);
    recomputeSchedule(defaultTemplateId, (watchedDate ?? dayjs()).format(API_DATE_FORMAT));
  }

  return {
    autoAssignEnabled, selectedTemplateId, autoAssignDates, autoAssignSelected, watchedDate,
    setSelectedTemplateId, setAutoAssignDates, setAutoAssignSelected, recomputeSchedule, handleAutoAssignToggle,
  };
}
