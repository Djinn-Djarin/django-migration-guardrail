from datetime import datetime
from html import escape
from pathlib import Path


DEFAULT_REPORT_PATH = "migration_guardrail_report.html"


def resolve_report_path(path):
    """Return the report path, using a default filename when only the flag is set."""
    return Path(path or DEFAULT_REPORT_PATH)


def write_html_report(path, title, migration_rows, migration_issues, schema_rows=None):
    """Write a standalone HTML report for migration and schema guardrail results."""
    report_path = resolve_report_path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    schema_rows = schema_rows or []

    migration_status = "failed" if migration_issues else "passed"
    schema_issues = [row for row in schema_rows if row["issue"]]
    schema_status = "failed" if schema_issues else "passed"

    report_path.write_text(
        _render_html(
            title=title,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            migration_status=migration_status,
            schema_status=schema_status,
            migration_rows=migration_rows,
            schema_rows=schema_rows,
        ),
        encoding="utf-8",
    )
    return report_path


def _render_html(title, generated_at, migration_status, schema_status, migration_rows, schema_rows):
    migration_body = "\n".join(_render_migration_row(row) for row in migration_rows)
    schema_body = "\n".join(_render_schema_row(row) for row in schema_rows)

    if not migration_body:
        migration_body = '<tr><td colspan="5" class="empty">No project migrations found.</td></tr>'
    if not schema_body:
        schema_body = '<tr><td colspan="3" class="empty">No schema discrepancies found.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    h1 {{ margin-bottom: 4px; }}
    h2 {{ margin-top: 32px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    .meta {{ color: #6b7280; margin-top: 0; }}
    .passed {{ color: #047857; font-weight: 700; }}
    .failed {{ color: #b91c1c; font-weight: 700; }}
    .issue {{ background: #fef2f2; }}
    .empty {{ color: #6b7280; text-align: center; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p class="meta">Generated at {escape(generated_at)}</p>

  <h2>Summary</h2>
  <p>Migration history: <span class="{migration_status}">{migration_status.upper()}</span></p>
  <p>Database schema: <span class="{schema_status}">{schema_status.upper()}</span></p>

  <h2>Migration History</h2>
  <table>
    <thead>
      <tr>
        <th>App</th>
        <th>Migration</th>
        <th>In Code</th>
        <th>In DB</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {migration_body}
    </tbody>
  </table>

  <h2>Database Schema</h2>
  <table>
    <thead>
      <tr>
        <th>Table</th>
        <th>Field/Column</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {schema_body}
    </tbody>
  </table>
</body>
</html>
"""


def _render_migration_row(row):
    css_class = ' class="issue"' if row["issue"] else ""
    return (
        f"<tr{css_class}>"
        f"<td>{escape(row['app'])}</td>"
        f"<td>{escape(row['migration'])}</td>"
        f"<td>{'yes' if row['in_code'] else 'no'}</td>"
        f"<td>{'yes' if row['in_db'] else 'no'}</td>"
        f"<td>{escape(row['status'])}</td>"
        "</tr>"
    )


def _render_schema_row(row):
    css_class = ' class="issue"' if row["issue"] else ""
    return (
        f"<tr{css_class}>"
        f"<td>{escape(row['table'])}</td>"
        f"<td>{escape(row['field'])}</td>"
        f"<td>{escape(row['status'])}</td>"
        "</tr>"
    )
