// Shared by PlanningPage and StatisticsPage for their "Работа" column: applied as the antd
// column `width` (becomes a literal <col> width, which auto table layout treats as a floor,
// not a cap) and, together with `overflow-wrap: anywhere` on the cell text, as a real cap —
// without the wrap, an unbroken long string forces the column wider regardless of this value.
export const NAME_COLUMN_WIDTH = 'clamp(320px, 32vw, 640px)';
