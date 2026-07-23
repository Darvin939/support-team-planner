## MODIFIED Requirements

### Requirement: DAO writes commit only via the decorator

Every DAO write function wrapped by `with_db_connection` SHALL rely solely on transaction infrastructure for
committing its writes: outside an explicit composite transaction the decorator SHALL commit on successful return,
while inside an explicit composite transaction the decorator SHALL defer commit to the enclosing transaction
scope. No wrapped DAO function SHALL call `conn.commit()` itself.

#### Scenario: create_team commits exactly once outside a composite transaction

- **WHEN** `create_team` is called outside an explicit composite transaction and succeeds
- **THEN** the new row is committed and visible to other connections immediately after `create_team` returns,
  with exactly one `conn.commit()` call happening inside the decorator

#### Scenario: DAO writes defer commit inside a composite transaction

- **WHEN** two or more write functions wrapped by `with_db_connection` succeed inside one explicit composite
  transaction
- **THEN** none of the individual decorators commits and the enclosing transaction scope performs exactly one
  commit after all steps succeed

#### Scenario: Result value doesn't depend on commit timing

- **WHEN** `create_team`, `create_segment`, `create_block`, `create_template`, or `create_or_update_task` reads
  back a value it just wrote before returning
- **THEN** that read succeeds correctly whether commit is performed by the decorator or deferred to an enclosing
  transaction, since it reads on the same connection
