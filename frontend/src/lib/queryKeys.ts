export const queryKeys = {
  me: ['me'] as const,
  teams: ['teams'] as const,
  paginatedTeams: (offset: number, limit: number, search: string) =>
    ['teams', 'paginated', offset, limit, search] as const,
  users: {
    all: ['users'] as const,
    paginated: (offset: number, limit: number, search: string) => ['users', 'paginated', offset, limit, search] as const,
    assignees: (teamId: number) => ['team-assignees', teamId] as const,
  },
  tasks: {
    all: ['tasks'] as const,
    list: (teamId: number, offset: number, limit: number, search: string, showCompleted: boolean) =>
      ['tasks', teamId, offset, limit, search, showCompleted] as const,
    byId: (teamId: number, taskId: number | null) => ['tasks', teamId, 'byId', taskId] as const,
  },
  assignments: {
    all: ['assignments'] as const,
    list: (teamId: number, from: string, to: string, taskIds: number[]) => ['assignments', teamId, from, to, taskIds] as const,
    active: ['active-assignments'] as const,
    activeList: (from: string, to: string, teamIds: number[], offset: number, limit: number) =>
      ['active-assignments', from, to, teamIds, offset, limit] as const,
  },
  taskDeps: ['task-deps'] as const,
  taskDepsList: (teamId: number, taskIds: number[]) => ['task-deps', teamId, taskIds] as const,
  dependencyGraph: ['dependency-graph'] as const,
  dependencyGraphFor: (teamId: number, taskId?: number) => ['dependency-graph', teamId, taskId ?? null] as const,
  teamBlocks: (teamId: number, segmentId?: number | null) => ['team-blocks', teamId, segmentId ?? null] as const,
  teamTemplates: (teamId: number) => ['team-templates', teamId] as const,
  activeTasks: (teamId: number, search: string, includeIds: string) => ['active-tasks-list', teamId, search, includeIds] as const,
  journal: (teamId: number | undefined, offset: number, filters: object) => ['journal', teamId, offset, filters] as const,
  taskHistory: (taskId: number | null, offset: number) => ['task-history', taskId, offset] as const,
  entityHistory: (kind: string, entityId: number | null, offset: number) => ['entity-history', kind, entityId, offset] as const,
  blocks: ['blocks'] as const,
  blockTemplates: ['block-templates'] as const,
  freezeDays: ['freeze-days'] as const,
  segments: ['segments'] as const,
} as const;
