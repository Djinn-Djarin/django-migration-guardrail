import unittest
from unittest.mock import patch

from django.core.management.base import CommandError

from migration_guardrail.management.commands.migrate import Command


class MigrateCommandTests(unittest.TestCase):
    def test_html_report_requires_sync(self):
        command = Command()

        with self.assertRaises(CommandError) as exc:
            command.handle(sync=False, html_report="report.html")

        self.assertEqual(
            str(exc.exception),
            "--html-report can only be used with --sync on the migrate command.",
        )

    @patch("migration_guardrail.management.commands.migrate.call_command")
    @patch("migration_guardrail.management.commands.migrate.DjangoMigrateCommand.handle")
    @patch("migration_guardrail.management.commands.migrate.Command._check_migration_history")
    def test_sync_runs_preflight_migrate_and_postflight(
        self,
        check_history_mock,
        django_handle_mock,
        call_command_mock,
    ):
        command = Command()
        django_handle_mock.return_value = "migrated"

        result = command.handle(sync=True, html_report="report.html")

        self.assertEqual(result, "migrated")
        check_history_mock.assert_called_once_with()
        django_handle_mock.assert_called_once_with()
        self.assertEqual(
            call_command_mock.call_args_list,
            [
                unittest.mock.call("check"),
                unittest.mock.call("migration_guardrail_sync", html_report="report.html"),
            ],
        )

    @patch("migration_guardrail.management.commands.migrate.call_command")
    @patch("migration_guardrail.management.commands.migrate.DjangoMigrateCommand.handle")
    @patch("migration_guardrail.management.commands.migrate.Command._check_migration_history")
    def test_plain_migrate_delegates_to_django_only(
        self,
        check_history_mock,
        django_handle_mock,
        call_command_mock,
    ):
        command = Command()
        django_handle_mock.return_value = "migrated"

        result = command.handle(sync=False, html_report=None)

        self.assertEqual(result, "migrated")
        check_history_mock.assert_not_called()
        call_command_mock.assert_not_called()
        django_handle_mock.assert_called_once_with()
