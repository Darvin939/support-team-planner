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


if __name__ == '__main__':
    unittest.main()
