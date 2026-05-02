"""Django command entry point for ``manage.py migration_guardrail_sync``.

Django discovers management commands from ``management/commands`` modules. The
real implementation lives in ``migration_guardrail.sync`` so it can stay outside
the command-discovery package and remain easier to reuse or test.
"""

from migration_guardrail.sync import Command
