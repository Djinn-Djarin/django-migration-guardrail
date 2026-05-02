"""Full Migration Guardrail sync command implementation.

The public Django command wrapper is
``migration_guardrail.management.commands.migration_guardrail_sync``. This module
contains the real command logic so command discovery stays separate from the
checks and reporting workflow.
"""

import sys

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from migration_guardrail.checks import build_migration_report, get_project_app_configs
from migration_guardrail.reports import DEFAULT_REPORT_PATH, write_html_report


class Command(BaseCommand):
    """Check system health, migration history, and model/database schema drift."""

    help = "Run Django checks, migration history checks, and database schema sync checks."

    def add_arguments(self, parser):
        parser.add_argument(
            "--html-report",
            nargs="?",
            const=DEFAULT_REPORT_PATH,
            help=(
                "Write an HTML report. Optionally pass a path. "
                f"Default: {DEFAULT_REPORT_PATH}"
            ),
        )

    def handle(self, *args, **options):
        report_path = options.get("html_report")

        self.stdout.write(self.style.MIGRATE_HEADING("\n[1/3] Running Django System Checks..."))

        try:
            call_command("check")
            self.stdout.write(self.style.SUCCESS("System check identified no issues."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"System check failed: {e}"))
            sys.exit(1)

        self.stdout.write(self.style.MIGRATE_HEADING("\n[2/3] Running Project Migration History Check..."))
        migration_issues = self._check_migration_history()

        self.stdout.write(self.style.MIGRATE_HEADING("\n[3/3] Running Database Reality Check..."))
        self.stdout.write("-" * 100)
        self.stdout.write(f"{'TABLE NAME':<40} | {'FIELD/COLUMN':<30} | {'ERROR TYPE'}")
        self.stdout.write("-" * 100)

        mismatches = []
        schema_rows = []

        for app_config in get_project_app_configs():
            for model in app_config.get_models():
                table_name = model._meta.db_table
                model_fields = {field.column.lower() for field in model._meta.fields}

                with connection.cursor() as cursor:
                    try:
                        description = connection.introspection.get_table_description(cursor, table_name)
                        db_columns = {col.name.lower() for col in description}
                    except Exception:
                        msg = f"{table_name:<40} | {'(All Fields)':<30} |  TABLE MISSING IN DB"
                        self.stdout.write(self.style.ERROR(msg))
                        mismatches.append(msg)
                        schema_rows.append(
                            {
                                "table": table_name,
                                "field": "(All Fields)",
                                "status": "TABLE MISSING IN DB",
                                "issue": True,
                            }
                        )
                        continue

                for field in model_fields - db_columns:
                    msg = f"{table_name:<40} | {field:<30} |  FIELD MISSING IN DB"
                    self.stdout.write(self.style.WARNING(msg))
                    mismatches.append(msg)
                    schema_rows.append(
                        {
                            "table": table_name,
                            "field": field,
                            "status": "FIELD MISSING IN DB",
                            "issue": True,
                        }
                    )

                for col in db_columns - model_fields:
                    if col == "id" and "id" not in model_fields:
                        continue
                    msg = f"{table_name:<40} | {col:<30} |  GHOST COLUMN IN DB"
                    self.stdout.write(self.style.NOTICE(msg))
                    mismatches.append(msg)
                    schema_rows.append(
                        {
                            "table": table_name,
                            "field": col,
                            "status": "GHOST COLUMN IN DB",
                            "issue": True,
                        }
                    )

        self.stdout.write("-" * 100)

        if report_path:
            # Write the report before raising so users still get a downloadable
            # artifact when the guardrail finds discrepancies.
            written_path = write_html_report(
                report_path,
                "Migration Guardrail Sync Report",
                self._migration_rows,
                self._migration_issues,
                schema_rows,
            )
            self.stdout.write(self.style.SUCCESS(f"HTML report written to {written_path}"))

        if migration_issues or mismatches:
            issue_count = len(migration_issues) + len(mismatches)
            raise CommandError(f"Sync check failed: found {issue_count} discrepancy(s).")

        self.stdout.write(self.style.SUCCESS("Project and database are in sync."))

    def _check_migration_history(self):
        """Print migration-history rows and keep them for optional HTML reports."""
        rows, issues = build_migration_report()
        self._migration_rows = rows
        self._migration_issues = issues

        self.stdout.write("-" * 120)
        self.stdout.write(
            f"{'APP':<24} | {'MIGRATION':<38} | {'IN CODE':<7} | {'IN DB':<5} | {'STATUS'}"
        )
        self.stdout.write("-" * 120)

        for row in rows:
            msg = (
                f"{row['app']:<24} | "
                f"{row['migration']:<38} | "
                f"{'yes' if row['in_code'] else 'no':<7} | "
                f"{'yes' if row['in_db'] else 'no':<5} | "
                f"{row['status']}"
            )
            if row["issue"]:
                self.stdout.write(self.style.ERROR(msg))
            elif row["status"] == "OK":
                self.stdout.write(msg)
            else:
                self.stdout.write(self.style.NOTICE(msg))

        self.stdout.write("-" * 120)

        if issues:
            self.stdout.write(
                self.style.ERROR(
                    f"Migration history check failed: found {len(issues)} discrepancy(s)."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Project migration files and DB history are in sync."))

        return issues
