import type {AssignmentStatus} from '../../domain/types';


export function canChangeAssignmentStatus(isUser: boolean): boolean {
  return !isUser;
}

export function assignmentStatusForSave(
  isUser: boolean,
  requestedStatus: AssignmentStatus,
): AssignmentStatus {
  return isUser ? 'new' : requestedStatus;
}
