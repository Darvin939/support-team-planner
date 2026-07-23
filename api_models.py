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
