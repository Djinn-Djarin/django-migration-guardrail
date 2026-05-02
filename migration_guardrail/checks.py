import site
import sys
from pathlib import Path

from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder


def _migration_replacements(disk_migrations, project_labels):
    """Return lookup maps for squashed migrations and the migrations they replace."""
    squash_replaces = {}
    replaced_by = {}

    for key, migration in disk_migrations.items():
        app_label, _ = key
        if app_label not in project_labels:
            continue

        replacements = tuple(
            replacement
            for replacement in getattr(migration, "replaces", ()) or ()
            if replacement[0] in project_labels
        )
        if not replacements:
            continue

        # Django stores squash relationships on the squashed migration via
        # ``replaces``. Keep both directions so later checks can treat either
        # side as satisfying the same migration history.
        squash_replaces[key] = replacements
        for replacement in replacements:
            replaced_by[replacement] = key

    return squash_replaces, replaced_by


def _is_migration_satisfied(key, db_migrations, squash_replaces, replaced_by):
    """Return whether a migration is applied directly or covered by a squash."""
    if key in db_migrations:
        return True

    replacements = squash_replaces.get(key)
    if replacements and all(replacement in db_migrations for replacement in replacements):
        return True

    squash_key = replaced_by.get(key)
    if squash_key and squash_key in db_migrations:
        return True

    return False


def _find_dependency_issues(
    disk_migrations,
    db_migrations,
    project_labels,
    squash_replaces,
    replaced_by,
):
    """Find applied migrations whose project dependencies are not satisfied."""
    issues = []

    for key, migration in sorted(disk_migrations.items()):
        # Only migrations that are already satisfied can expose inconsistent
        # history. Unapplied migrations are reported by the main row builder.
        if not _is_migration_satisfied(key, db_migrations, squash_replaces, replaced_by):
            continue

        for dependency in getattr(migration, "dependencies", ()) or ():
            # Ignore dependencies outside the project and Django's special
            # internal dependency markers such as ("app", "__first__").
            if dependency[0] not in project_labels or dependency[1].startswith("__"):
                continue
            if _is_migration_satisfied(dependency, db_migrations, squash_replaces, replaced_by):
                continue

            issues.append(
                {
                    "app": key[0],
                    "migration": key[1],
                    "in_code": True,
                    "in_db": key in db_migrations,
                    "status": (
                        "INCONSISTENT HISTORY: missing dependency "
                        f"{dependency[0]}.{dependency[1]}"
                    ),
                    "issue": True,
                }
            )

    return issues


def build_migration_history_rows(disk_migrations, db_migrations, project_labels):
    """Build display rows and issue rows for code-vs-database migration state.

    Args:
        disk_migrations: MigrationLoader.disk_migrations-style mapping.
        db_migrations: Iterable of applied migration keys from django_migrations.
        project_labels: App labels that should be checked.

    Returns:
        A tuple of ``(rows, issues)``. Every item is a dict ready for command
        output, and ``issues`` contains the subset that should fail the check.
    """
    disk_migrations = {
        key: migration
        for key, migration in disk_migrations.items()
        if key[0] in project_labels
    }
    db_migrations = {key for key in db_migrations if key[0] in project_labels}
    squash_replaces, replaced_by = _migration_replacements(disk_migrations, project_labels)

    rows = []
    issues = []
    all_keys = set(disk_migrations) | db_migrations

    for key in sorted(all_keys):
        in_code = key in disk_migrations
        in_db = key in db_migrations
        replacements = squash_replaces.get(key, ())
        squash_key = replaced_by.get(key)
        issue = False

        # A migration can be healthy because it exists both in code and DB, or
        # because Django's squash metadata proves an equivalent migration path.
        if in_code and in_db:
            status = "OK"
        elif in_code and replacements and all(replacement in db_migrations for replacement in replacements):
            status = "SATISFIED BY REPLACED MIGRATIONS"
        elif in_code and replacements and any(replacement in db_migrations for replacement in replacements):
            status = "PARTIAL SQUASHED MIGRATION"
            issue = True
        elif in_code and squash_key and squash_key in db_migrations:
            status = "REPLACED BY APPLIED SQUASHED MIGRATION"
        elif in_code:
            status = "MIGRATION NOT APPLIED IN DB"
            issue = True
        elif in_db and squash_key:
            status = "REPLACED BY SQUASHED MIGRATION"
        elif in_db:
            status = "MIGRATION MISSING ON DISK"
            issue = True
        else:
            status = "UNKNOWN"
            issue = True

        row = {
            "app": key[0],
            "migration": key[1],
            "in_code": in_code,
            "in_db": in_db,
            "status": status,
            "issue": issue,
        }
        rows.append(row)
        if issue:
            issues.append(row)

    # Dependency consistency needs the squash lookup tables built above, so it
    # runs after the per-migration status pass.
    dependency_issues = _find_dependency_issues(
        disk_migrations,
        db_migrations,
        project_labels,
        squash_replaces,
        replaced_by,
    )
    rows.extend(dependency_issues)
    issues.extend(dependency_issues)

    rows.sort(key=lambda row: (row["app"], row["migration"], row["status"]))
    return rows, issues


def _is_project_app(app_config, project_root):
    """Return whether an app's source directory is inside the Django project."""
    app_path = Path(app_config.path).resolve()

    if app_config.name.startswith("django.") or _is_environment_path(app_path):
        return False

    try:
        return app_path.is_relative_to(project_root)
    except AttributeError:
        return project_root == app_path or project_root in app_path.parents


def _is_environment_path(path):
    """Return whether a path belongs to Python/virtualenv installed packages."""
    environment_roots = {Path(sys.prefix).resolve(), Path(sys.exec_prefix).resolve()}

    try:
        environment_roots.update(Path(item).resolve() for item in site.getsitepackages())
    except AttributeError:
        pass

    try:
        environment_roots.add(Path(site.getusersitepackages()).resolve())
    except AttributeError:
        pass

    if any(_path_contains(path, root) for root in environment_roots):
        return True

    # A project-local virtualenv lives inside the project root, so a simple
    # "inside current working directory" check would otherwise include all of
    # its third-party apps.
    return any(part in {".venv", "venv", "env", "site-packages", "dist-packages"} for part in path.parts)


def _path_contains(path, root):
    """Return whether path is equal to or nested under root."""
    try:
        return path == root or path.is_relative_to(root)
    except AttributeError:
        return path == root or root in path.parents


def get_project_app_configs():
    """Return installed app configs that belong to the current project checkout.

    Third-party apps also ship migrations, but Guardrail should not report on
    package-owned migration histories such as django_celery_beat or
    token_blacklist. In normal Django usage, management commands run from the
    directory containing manage.py, so apps under that directory are treated as
    project apps.
    """
    project_root = Path.cwd().resolve()
    return [
        app_config
        for app_config in apps.get_app_configs()
        if _is_project_app(app_config, project_root)
    ]


def get_project_labels():
    """Return app labels for project-owned apps only."""
    return {
        app_config.label
        for app_config in get_project_app_configs()
    }


def build_migration_report(project_labels=None):
    """Load current Django migration state and build a guardrail report."""
    if project_labels is None:
        project_labels = get_project_labels()

    loader = MigrationLoader(connection, ignore_no_migrations=True)
    applied = MigrationRecorder(connection).applied_migrations()

    if hasattr(applied, "keys"):
        applied = applied.keys()

    return build_migration_history_rows(
        loader.disk_migrations,
        set(applied),
        project_labels,
    )
