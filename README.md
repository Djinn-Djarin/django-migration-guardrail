# Django Migrations Guardrail

Django app that adds migration and database sync guardrails to a project.

It extends Django's normal `migrate` command with a `--sync` option:

```bash
python manage.py migrate --sync
```

That command runs safe pre-migration checks first, applies pending migrations,
then verifies the final database state.

- Django system checks
- migration files vs `django_migrations`
- model fields vs database columns

## Background

This package is motivated by a common Django failure mode: the database schema,
the `django_migrations` table, and migration files can drift apart after manual
database edits, deleted migration files, edited old migrations, or faked
migrations.

As discussed in this Django Forum thread, migration files should be treated as
critical project code, not disposable generated files:

https://forum.djangoproject.com/t/database-out-of-sync-with-migrations/30358/7

`django-migrations-guardrail` helps detect those sync problems before they turn
into confusing production errors.

## Features

- Adds `python manage.py migrate --sync`
- Runs pre-migration checks before applying migrations
- Applies pending migrations only if preflight checks pass
- Runs full database sync checks after migrations succeed
- Runs Django's built-in system checks
- Checks project migration files against the `django_migrations` table
- Ignores third-party package migrations such as `django_celery_beat`, `sessions`, and `token_blacklist`
- Detects migrations that exist in code but are not applied in the database
- Detects migrations recorded in the database but missing from code
- Supports squashed migrations through Django's `replaces` metadata
- Detects inconsistent migration dependencies
- Checks model fields against real database columns
- Reports missing database tables
- Reports fields missing from the database
- Reports database columns that no longer exist in models
- Writes an HTML report with `--html-report`
- Installs directly from GitLab without publishing to PyPI

## Installation

If your Django project uses `uv`, add the `dev` branch as a dependency:

```bash
uv add "django-migrations-guardrail @ git+ssh://git@gitlab.decipherzone.com/divendra.pathak/django-migrations-gaurdrail.git@dev"
```

This updates your project's `pyproject.toml` and lock file.

If you want to install into a virtualenv without updating project dependencies,
use `uv pip`:

```bash
uv pip install --python .venv/bin/python "git+ssh://git@gitlab.decipherzone.com/divendra.pathak/django-migrations-gaurdrail.git@dev"
```

If you do not use `uv`, install with `pip` from an activated virtualenv:

```bash
python -m pip install "git+ssh://git@gitlab.decipherzone.com/divendra.pathak/django-migrations-gaurdrail.git@dev"
```

If your virtualenv does not have `pip`, install pip first:

```bash
python -m ensurepip --upgrade
python -m pip install --upgrade pip
python -m pip install "git+ssh://git@gitlab.decipherzone.com/divendra.pathak/django-migrations-gaurdrail.git@dev"
```

Install a specific tag instead of `dev` for stable releases with `uv add`:

```bash
uv add "django-migrations-guardrail @ git+ssh://git@gitlab.decipherzone.com/divendra.pathak/django-migrations-gaurdrail.git@v0.1.0"
```

Or install a tag into a virtualenv with `uv pip`:

```bash
uv pip install --python .venv/bin/python "git+ssh://git@gitlab.decipherzone.com/divendra.pathak/django-migrations-gaurdrail.git@v0.1.0"
```

Or with `pip`:

```bash
python -m pip install "git+ssh://git@gitlab.decipherzone.com/divendra.pathak/django-migrations-gaurdrail.git@v0.1.0"
```

Install from a local checkout while developing:

```bash
uv add --editable /path/to/django-migration-guardrail
```

Or install the local checkout into a specific virtualenv:

```bash
uv pip install --python /path/to/project/.venv/bin/python -e /path/to/django-migration-guardrail
```

## Django Setup

Add the app to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "migration_guardrail",
]
```

Check that Django sees the custom option:

```bash
python manage.py migrate --help
```

You should see:

```text
--sync
```

## Usage

Use this before deployment or after pulling code changes:

```bash
python manage.py migrate --sync
```

This command:

- runs preflight checks
- applies pending migrations if preflight passes
- runs full sync checks after migration succeeds

If preflight checks fail, migrations are not applied. If migrations fail,
post-migration checks do not run. If everything succeeds, the package confirms
your code, migration history, and database schema are aligned.

Use `migration_guardrail_sync` when you want the full check without applying
migrations:

```bash
python manage.py migration_guardrail_sync
```

This command runs Django system checks, migration-history checks, and model vs
database schema checks. It does not apply migrations.

## HTML Reports

Write an HTML report after `migrate --sync`:

```bash
python manage.py migrate --sync --html-report
```

By default this creates:

```text
migration_guardrail_report.html
```

Write the HTML report to a custom path:

```bash
python manage.py migrate --sync --html-report reports/migration_guardrail.html
```

Download the full sync report as HTML:

```bash
python manage.py migration_guardrail_sync --html-report reports/migration_sync.html
```

## Package Names

Install/package name:

```text
django-migrations-guardrail
```

Django app/import name:

```python
"migration_guardrail"
```
