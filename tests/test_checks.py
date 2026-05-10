import unittest
from types import SimpleNamespace

from migration_guardrail.checks import build_migration_history_rows


class BuildMigrationHistoryRowsTests(unittest.TestCase):
    def test_reports_missing_database_migration(self):
        disk_migrations = {
            ("billing", "0001_initial"): SimpleNamespace(dependencies=(), replaces=()),
        }

        rows, issues = build_migration_history_rows(
            disk_migrations=disk_migrations,
            db_migrations=set(),
            project_labels={"billing"},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "MIGRATION NOT APPLIED IN DB")
        self.assertEqual(issues, rows)

    def test_treats_applied_squashed_migration_as_satisfied(self):
        disk_migrations = {
            ("billing", "0001_initial"): SimpleNamespace(dependencies=(), replaces=()),
            (
                "billing",
                "0002_squashed",
            ): SimpleNamespace(
                dependencies=(),
                replaces=(("billing", "0001_initial"),),
            ),
        }

        rows, issues = build_migration_history_rows(
            disk_migrations=disk_migrations,
            db_migrations={("billing", "0002_squashed")},
            project_labels={"billing"},
        )

        status_by_key = {(row["app"], row["migration"]): row["status"] for row in rows}
        self.assertEqual(
            status_by_key[("billing", "0001_initial")],
            "REPLACED BY APPLIED SQUASHED MIGRATION",
        )
        self.assertEqual(status_by_key[("billing", "0002_squashed")], "OK")
        self.assertEqual(issues, [])

    def test_reports_inconsistent_dependency_history(self):
        disk_migrations = {
            ("orders", "0001_initial"): SimpleNamespace(dependencies=(), replaces=()),
            (
                "orders",
                "0002_items",
            ): SimpleNamespace(
                dependencies=(("orders", "0001_initial"),),
                replaces=(),
            ),
        }

        rows, issues = build_migration_history_rows(
            disk_migrations=disk_migrations,
            db_migrations={("orders", "0002_items")},
            project_labels={"orders"},
        )

        statuses = [row["status"] for row in rows]
        self.assertIn("MIGRATION NOT APPLIED IN DB", statuses)
        self.assertIn(
            "INCONSISTENT HISTORY: missing dependency orders.0001_initial",
            statuses,
        )
        self.assertEqual(len(issues), 2)
