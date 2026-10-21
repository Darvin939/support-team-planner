## MODIFIED Requirements

### Requirement: Assignment timelines use a shared bounded date-grid layout
Task cards for works of every status and expandable archive rows SHALL expose a read-only assignment timeline using the shared `PlanningDateGrid` layout primitive. The timeline SHALL show all non-deleted assignments of the work, regardless of assignment status and independently of the planning page's selected date range. The primitive SHALL provide bounded horizontal scrolling, click-and-drag panning without text selection or browser context menus, sticky opaque first-column layering, and safe rendering inside modal/expanded-row width constraints. The auto-scheduling grid SHALL reuse this layout and drag-scroll mechanism while retaining its own interactive draggable block behavior.

#### Scenario: Timeline remains inside an archive modal
- **WHEN** an expanded archive task has assignments spanning more dates than fit in the modal
- **THEN** the expanded row remains constrained to the modal width and the timeline scrolls horizontally inside it

#### Scenario: Timeline groups blocks and status by date
- **WHEN** a date has one or more non-deleted assignments
- **THEN** one group is rendered for that date, block names are comma-separated on the first line, and one localized status is rendered on the second line

#### Scenario: Timeline labels and sticky column
- **WHEN** the timeline is rendered and horizontally scrolled
- **THEN** the first-column labels are `Дата` and `Блок`, and the first column remains readable above date cells

#### Scenario: Grid drag does not select content
- **WHEN** the user pans either date grid with a mouse drag
- **THEN** text selection and the browser context menu are suppressed for the drag gesture

#### Scenario: Active task card shows its full assignment timeline
- **WHEN** a user opens the card of an existing work that is not completed or cancelled
- **THEN** the main tab shows the read-only timeline for all its non-deleted assignments, regardless of the planning page's selected date range

#### Scenario: Archive timeline includes every assignment status
- **WHEN** a user expands an archived work with non-deleted assignments of any statuses
- **THEN** the timeline shows those assignments grouped by date with their localized status
