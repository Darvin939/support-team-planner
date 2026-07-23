import {useEffect, useState} from 'react';
import {message} from 'antd';
import dayjs from 'dayjs';
import type {Assignment, Task} from '../../hooks/usePlanningData';
import {useAssignments, useTaskById} from '../../hooks/usePlanningData';
import {API_DATE_FORMAT} from '../../lib/dateFormats';

interface JumpState {
  jumpTaskId?: number;
  jumpDate?: string;
}

export function usePlanningNavigation(options: {
  teamId: number;
  jump: JumpState | null;
  clearJump: () => void;
  openAssignment: (task: Task, date: string, assignment: Assignment | null) => void;
  openTask: (task: Task) => void;
}) {
  const [depJumpTaskId, setDepJumpTaskId] = useState<number | null>(null);
  const {jump, teamId, clearJump, openAssignment, openTask} = options;
  const {data: jumpTask} = useTaskById(teamId, jump?.jumpTaskId ?? null);
  const {data: jumpAssignments} = useAssignments(
    teamId,
    jump?.jumpDate ? dayjs(jump.jumpDate).subtract(60, 'day').format(API_DATE_FORMAT) : '',
    jump?.jumpDate ? dayjs(jump.jumpDate).add(60, 'day').format(API_DATE_FORMAT) : '',
    jump?.jumpTaskId ? [jump.jumpTaskId] : [],
  );
  const {data: depJumpTask, isFetched: depJumpFetched} = useTaskById(teamId, depJumpTaskId);

  useEffect(() => {
    if (!jump?.jumpTaskId || !jump.jumpDate || !jumpTask) return;
    const assignment = (jumpAssignments ?? []).find((item) => item.date === jump.jumpDate) ?? null;
    openAssignment(jumpTask, jump.jumpDate, assignment);
    clearJump();
  }, [jump, jumpTask, jumpAssignments, openAssignment, clearJump]);

  useEffect(() => {
    if (!depJumpTaskId || !depJumpFetched) return;
    if (depJumpTask) openTask(depJumpTask);
    else message.info('Задача не найдена');
    setDepJumpTaskId(null);
  }, [depJumpTaskId, depJumpTask, depJumpFetched, openTask]);

  return {depJumpTaskId, setDepJumpTaskId, jumpAssignments};
}
