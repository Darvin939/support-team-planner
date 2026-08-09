## MODIFIED Requirements

### Requirement: Router сохраняет method-dependent role policy

Явные зависимости FastAPI на route-группе или конкретном endpoint SHALL сохранять различающиеся по операциям требования к роли и предоставлять handler проверенного текущего session user без зависимости политики от строкового сопоставления HTTP-метода и URL-пути в общем middleware.

#### Scenario: Чтение пользователей
- **WHEN** не-admin авторизованный пользователь вызывает GET `/api/users`
- **THEN** запрос остаётся доступен в прежнем full-list или paginated режиме

#### Scenario: Изменение пользователей
- **WHEN** роль ниже admin вызывает mutation `/api/users`
- **THEN** явно назначенная endpoint-зависимость отклоняет запрос по прежнему контракту

#### Scenario: Удаление пользователя
- **WHEN** admin удаляет пользователя
- **THEN** handler передаёт id проверенного текущего пользователя в доменную операцию

