## ADDED Requirements

### Requirement: Router сохраняет method-dependent role policy

Перемещение route-группы в `APIRouter` SHALL сохранять различающиеся по HTTP-методу требования к роли и
использование текущего session user в handler.

#### Scenario: Чтение пользователей
- **WHEN** не-admin авторизованный пользователь вызывает GET `/api/users`
- **THEN** запрос остаётся доступен в прежнем full-list или paginated режиме

#### Scenario: Изменение пользователей
- **WHEN** роль ниже admin вызывает mutation `/api/users`
- **THEN** middleware отклоняет запрос по прежнему контракту

#### Scenario: Удаление пользователя
- **WHEN** admin удаляет пользователя
- **THEN** handler передаёт id текущего session user в доменную операцию
