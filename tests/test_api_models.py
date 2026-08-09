import unittest

from support_planner import app


REQUEST_SCHEMA_NAMES = {
    'AssignmentIn',
    'AssignmentRescheduleIn',
    'BlockIn',
    'BlockTemplateIn',
    'BulkAssignmentRescheduleIn',
    'FreezeDayIn',
    'FreezeDayMonthIn',
    'MyPasswordIn',
    'SegmentIn',
    'TaskDependencyIn',
    'TaskIn',
    'TaskPriorityIn',
    'TaskReorderIn',
    'TaskStatusIn',
    'TeamIn',
    'TemplateEntryIn',
    'UserIn',
}


class ApiModelsContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = app.openapi()['components']['schemas']

    def test_request_schema_names_are_stable(self):
        self.assertTrue(REQUEST_SCHEMA_NAMES.issubset(self.schemas))

    def test_required_fields_and_defaults_are_stable(self):
        self.assertEqual(
            ['assignment_id', 'new_date'],
            self.schemas['AssignmentRescheduleIn']['required'],
        )
        self.assertEqual(
            ['moves'],
            self.schemas['BulkAssignmentRescheduleIn']['required'],
        )
        self.assertEqual(
            ['task_id', 'depends_on_task_id'],
            self.schemas['TaskDependencyIn']['required'],
        )
        self.assertEqual(
            ['year', 'month'],
            self.schemas['FreezeDayMonthIn']['required'],
        )
        self.assertEqual(
            'medium',
            self.schemas['TaskIn']['properties']['criticality']['default'],
        )
        self.assertEqual(
            True,
            self.schemas['UserIn']['properties']['is_assignee']['default'],
        )

    def test_nested_model_references_are_stable(self):
        moves = self.schemas['BulkAssignmentRescheduleIn']['properties']['moves']
        self.assertEqual(
            '#/components/schemas/AssignmentRescheduleIn',
            moves['items']['$ref'],
        )
        entries = self.schemas['BlockTemplateIn']['properties']['entries']['anyOf'][0]
        self.assertEqual(
            '#/components/schemas/TemplateEntryIn',
            entries['items']['$ref'],
        )

    def test_core_response_models_match_frontend_dto_fields(self):
        self.assertEqual(
            {
                'id', 'name', 'description', 'criticality', 'task_status', 'segment_id',
                'segment_name', 'completed_at', 'has_active_assignments',
            },
            set(self.schemas['TaskOut']['properties']),
        )
        self.assertEqual(
            {
                'id', 'task_id', 'date', 'block', 'status', 'user_id',
                'user_name', 'comment', 'time_spent',
            },
            set(self.schemas['AssignmentOut']['properties']),
        )

    def test_core_paths_publish_response_models(self):
        paths = app.openapi()['paths']
        expected = {
            ('/api/tasks/{team_id}', 'get'): 'TasksPage',
            ('/api/task/{task_id}', 'get'): 'TaskOut',
            ('/api/tasks/{team_id}/archive', 'get'): 'TasksPage',
            ('/api/task/{task_id}/history', 'get'): 'HistoryPage',
            ('/api/assignment/{assignment_id}/history', 'get'): 'HistoryPage',
            ('/api/active-assignments/{team_id}', 'get'): 'ActiveAssignmentsPage',
            ('/api/journal/{team_id}', 'get'): 'JournalPage',
        }
        for (path, method), schema_name in expected.items():
            with self.subTest(path=path):
                schema = paths[path][method]['responses']['200']['content']['application/json']['schema']
                self.assertEqual(f'#/components/schemas/{schema_name}', schema['$ref'])

    def test_reference_data_paths_and_methods_are_stable(self):
        paths = app.openapi()['paths']
        expected = {
            '/api/blocks': {'get', 'post'},
            '/api/blocks/{block_id}': {'delete'},
            '/api/block-templates': {'get', 'post'},
            '/api/block-templates/{template_id}': {'put', 'delete'},
            '/api/segments': {'get', 'post'},
            '/api/segments/{segment_id}': {'put', 'delete'},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertEqual(methods, set(paths[path]))

    def test_freeze_day_paths_and_methods_are_stable(self):
        paths = app.openapi()['paths']
        expected = {
            '/api/freeze-days': {'get', 'post'},
            '/api/freeze-days/month': {'put'},
            '/api/freeze-days/month/{year}/{month}': {'delete'},
            '/api/freeze-days/{date_str}': {'delete'},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertEqual(methods, set(paths[path]))

    def test_team_paths_and_methods_are_stable(self):
        paths = app.openapi()['paths']
        expected = {
            '/api/teams': {'get', 'post'},
            '/api/teams/{team_id}': {'get', 'put', 'delete'},
            '/api/teams/{team_id}/blocks': {'get'},
            '/api/teams/{team_id}/assignees': {'get'},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertEqual(methods, set(paths[path]))

    def test_user_paths_and_methods_are_stable(self):
        paths = app.openapi()['paths']
        self.assertEqual({'get', 'post'}, set(paths['/api/users']))
        self.assertEqual({'put', 'delete'}, set(paths['/api/users/{user_id}']))

    def test_assignment_paths_and_methods_are_stable(self):
        paths = app.openapi()['paths']
        expected = {
            '/api/assignments/{team_id}': {'get'},
            '/api/assignment': {'post'},
            '/api/assignments/bulk-reschedule': {'post'},
            '/api/assignment/{assignment_id}': {'delete'},
            '/api/assignment/{assignment_id}/history': {'get'},
            '/api/active-assignments/{team_id}': {'get'},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertEqual(methods, set(paths[path]))

    def test_task_dependency_paths_and_contract_are_stable(self):
        paths = app.openapi()['paths']
        expected = {
            '/api/tasks/{team_id}/deps': {'get'},
            '/api/tasks/{team_id}/dependency-graph': {'get'},
            '/api/task-dependency': {'post', 'delete'},
            '/api/tasks/{team_id}/active-list': {'get'},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertEqual(methods, set(paths[path]))

        deps_parameters = paths['/api/tasks/{team_id}/deps']['get']['parameters']
        self.assertEqual(['team_id', 'task_ids'], [item['name'] for item in deps_parameters])
        active_parameters = paths['/api/tasks/{team_id}/active-list']['get']['parameters']
        self.assertEqual(
            ['team_id', 'search', 'limit', 'include_ids'],
            [item['name'] for item in active_parameters],
        )
        for method in ('post', 'delete'):
            schema = paths['/api/task-dependency'][method]['requestBody']['content']['application/json']['schema']
            self.assertEqual('#/components/schemas/TaskDependencyIn', schema['$ref'])

    def test_shell_task_and_journal_paths_are_stable(self):
        paths = app.openapi()['paths']
        expected = {
            '/': {'get'},
            '/login': {'get', 'post'},
            '/logout': {'post'},
            '/api/me': {'get', 'put'},
            '/planning': {'get'},
            '/planning/{team_id}': {'get'},
            '/settings': {'get'},
            '/statistics': {'get'},
            '/journal': {'get'},
            '/journal/{team_id}': {'get'},
            '/api/tasks/{team_id}': {'get'},
            '/api/task/{task_id}': {'get', 'delete'},
            '/api/task/{task_id}/restore': {'post'},
            '/api/tasks/{team_id}/archive': {'get'},
            '/api/task': {'post'},
            '/api/tasks/{task_id}/status': {'patch'},
            '/api/tasks/{team_id}/reorder': {'patch'},
            '/api/task/{task_id}/priority': {'patch'},
            '/api/task/{task_id}/history': {'get'},
            '/api/journal/{team_id}': {'get'},
        }
        for path, methods in expected.items():
            with self.subTest(path=path):
                self.assertEqual(methods, set(paths[path]))

        task_list = paths['/api/tasks/{team_id}']['get']['parameters']
        self.assertEqual(
            ['team_id', 'offset', 'limit', 'search', 'include_recent_completed'],
            [parameter['name'] for parameter in task_list],
        )
        journal = paths['/api/journal/{team_id}']['get']['parameters']
        self.assertEqual(
            ['team_id', 'offset', 'limit', 'search', 'date_from', 'date_to', 'changed_by_user_id'],
            [parameter['name'] for parameter in journal],
        )
        body_schemas = {
            ('/api/task', 'post'): 'TaskIn',
            ('/api/tasks/{task_id}/status', 'patch'): 'TaskStatusIn',
            ('/api/tasks/{team_id}/reorder', 'patch'): 'TaskReorderIn',
            ('/api/task/{task_id}/priority', 'patch'): 'TaskPriorityIn',
        }
        for (path, method), schema_name in body_schemas.items():
            schema = paths[path][method]['requestBody']['content']['application/json']['schema']
            self.assertEqual(f'#/components/schemas/{schema_name}', schema['$ref'])


if __name__ == '__main__':
    unittest.main()
