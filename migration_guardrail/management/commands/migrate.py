"""Extension of Django's built-in ``migrate`` command.

This module must be named ``migrate.py`` so Django can let this app override the
default migrate command when ``migration_guardrail`` is in ``INSTALLED_APPS``.
The command keeps Django's normal migrate behavior and only adds ``--sync`` and
``--html-report`` options.
"""

from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as DjangoMigrateCommand

from migration_guardrail.checks import build_migration_report
from migration_guardrail.reports import DEFAULT_REPORT_PATH


class Command(DjangoMigrateCommand):
    """Run preflight checks, Django migrations, and post-migration verification."""

    help = DjangoMigrateCommand.help + " Use --sync to check, migrate, then verify with Migration Guardrail."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run preflight checks, apply pending migrations, then verify database sync.",
        )
        parser.add_argument(
            "--html-report",
            nargs="?",
            const=DEFAULT_REPORT_PATH,
            help="Write a post-migration HTML guardrail report when used with --sync.",
        )

    def handle(self, *args, **options):
        sync = options.pop("sync", False)
        html_report = options.pop("html_report", None)

        if html_report and not sync:
            raise CommandError("--html-report can only be used with --sync on the migrate command.")

        if sync:
            # Preflight avoids applying new migrations when migration history is
            # already inconsistent.
            self.stdout.write(self.style.MIGRATE_HEADING("Running pre-migration Guardrail checks..."))
            call_command("check")
            self._check_migration_history()
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Applying pending Django migrations..."))

        # Delegate the actual migration work to Django's original command.
        result = super().handle(*args, **options)

        if sync:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Django migration step completed successfully."))
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Running post-migration Guardrail sync checks..."))
            call_command("migration_guardrail_sync", html_report=html_report)

        return result

    def _check_migration_history(self):
        """Run the migration-history portion of Guardrail before applying migrations."""
        rows, issues = build_migration_report()

        self.stdout.write("-" * 120)
        self.stdout.write(
            f"{'APP':<24} | {'MIGRATION':<38} | {'IN CODE':<7} | {'IN DB':<5} | STATUS"
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
            else:
                self.stdout.write(msg)

        self.stdout.write("-" * 120)

        if issues:
            raise CommandError(
                f"Pre-migration Guardrail failed: found {len(issues)} migration issue(s)."
            )

        self.stdout.write(self.style.SUCCESS("Pre-migration Guardrail passed."))
