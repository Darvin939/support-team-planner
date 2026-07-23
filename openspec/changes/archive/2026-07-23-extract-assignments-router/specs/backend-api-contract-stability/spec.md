## ADDED Requirements

### Requirement: Router сохраняет общие domain rules

Если handlers разных route-групп используют одно доменное правило, декомпозиция SHALL оставлять единый helper и
сохранять результаты правила во всех потребителях.

#### Scenario: Заблокированная задача в assignment handler
- **WHEN** assignment mutation относится к завершённой, отменённой или удалённой задаче
- **THEN** router отклоняет операцию по прежнему task-lock правилу

#### Scenario: Та же задача в task handler
- **WHEN** task handler проверяет ту же задачу
- **THEN** он использует тот же domain helper и получает тот же результат

#### Scenario: CSV query filter после переноса
- **WHEN** task или assignment endpoint разбирает список id из CSV query parameter
- **THEN** оба endpoint используют один parser и сохраняют прежнее поведение пустых и заполненных значений

#### Scenario: Request context после переноса
- **WHEN** assignment mutation записывает историю
- **THEN** router передаёт прежний session user и сохраняет access checks
