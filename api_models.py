from typing import List, Optional, Union

from pydantic import BaseModel


class AssignmentIn(BaseModel):
    assignment_id: Optional[int] = None
    task_id: Optional[int] = None
    date: Optional[str] = None
    block: Optional[str] = None
    status: str = "new"
    user_id: Optional[int] = None
    comment: Optional[str] = None
    time_spent: Optional[str] = None


class AssignmentRescheduleIn(BaseModel):
    assignment_id: int
    new_date: str


class BulkAssignmentRescheduleIn(BaseModel):
    moves: List[AssignmentRescheduleIn]


class BulkAssignmentUpsertIn(BaseModel):
    assignments: List[AssignmentIn]


class BulkAssignmentResult(BaseModel):
    success: bool
    saved: int


class BulkAssignmentDeleteIn(BaseModel):
    assignment_ids: List[int]


class BulkAssignmentDeleteResult(BaseModel):
    success: bool
    deleted: int


class TaskOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    criticality: str
    task_status: str
    segment_id: int
    segment_name: str
    completed_at: Optional[str] = None
    has_active_assignments: bool


class TasksPage(BaseModel):
    tasks: List[TaskOut]
    total: int


class AssignmentOut(BaseModel):
    id: int
    task_id: int
    date: str
    block: Optional[str] = None
    status: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    comment: Optional[str] = None
    time_spent: Optional[str] = None


class HistoryEntryOut(BaseModel):
    id: int
    entity: Optional[str] = None
    action: Optional[str] = None
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    date: Optional[str] = None
    changed_at: Optional[str] = None
    changed_by_user_id: Optional[int] = None
    changed_by_last_name: Optional[str] = None
    changed_by_first_name: Optional[str] = None
    changed_by_middle_name: Optional[str] = None
    task_id: Optional[int] = None
    task_name: Optional[str] = None
    task_is_deleted: Optional[Union[bool, int]] = None


class HistoryPage(BaseModel):
    history: List[HistoryEntryOut]
    total: int


class JournalPage(BaseModel):
    items: List[HistoryEntryOut]
    total: int


class ActiveAssignmentOut(BaseModel):
    id: int
    task_id: int
    task_name: str
    criticality: str
    date: str
    block: Optional[str] = None
    status: str
    user_name: Optional[str] = None
    comment: Optional[str] = None
    team_id: int
    team_name: Optional[str] = None


class StatusCounts(BaseModel):
    new: int
    planned: int


class CriticalityCounts(BaseModel):
    high: int
    medium: int
    low: int


class ActiveAssignmentStats(BaseModel):
    status: StatusCounts
    criticality: CriticalityCounts


class ActiveAssignmentsPage(BaseModel):
    items: List[ActiveAssignmentOut]
    total: int
    stats: ActiveAssignmentStats


class TaskIn(BaseModel):
    task_id: Optional[Union[int, str]] = None
    team_id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    criticality: str = "medium"
    segment_id: Optional[int] = None
    dependency_ids: Optional[List[int]] = None


class TeamIn(BaseModel):
    name: str = ""
    template_ids: Optional[List[int]] = None


class BlockIn(BaseModel):
    name: str = ""


class SegmentIn(BaseModel):
    name: str = ""


class TemplateEntryIn(BaseModel):
    block_id: int
    shift_days: int = 0


class BlockTemplateIn(BaseModel):
    name: str = ""
    segment_id: Optional[int] = None
    entries: Optional[List[TemplateEntryIn]] = None


class UserIn(BaseModel):
    last_name: str = ""
    first_name: str = ""
    middle_name: Optional[str] = None
    password: Optional[str] = None
    role: str = "user"
    login: Optional[str] = None
    is_assignee: bool = True
    team_ids: Optional[List[int]] = None


class MyPasswordIn(BaseModel):
    password: Optional[str] = None


class FreezeDayIn(BaseModel):
    date: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class FreezeDayMonthIn(BaseModel):
    year: int
    month: int
    days: List[int] = []


class TaskStatusIn(BaseModel):
    status: str


class TaskReorderIn(BaseModel):
    task_ids: List[int]


class TaskPriorityIn(BaseModel):
    position: str


class TaskDependencyIn(BaseModel):
    task_id: int
    depends_on_task_id: int
