"""Report generation helper.

TODO(student): implement report rendering using MetricsReport data
and the template in reports/lab_report_template.md.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    TODO(student): Generate a report that includes:
    1. Metrics summary table (total scenarios, success rate, retries, interrupts)
    2. Per-scenario results table
    3. Architecture explanation (your graph design, state schema, reducers)
    4. Failure analysis (at least two failure modes you considered)
    5. Improvement plan

    Use reports/lab_report_template.md as your guide.

    Return: formatted markdown string
    """
    lines: list[str] = ["# Day 08 Lab Report", ""]

    lines += ["## 1. Team / student", "", "- Name: TODO(student)", "- Repo/commit: TODO(student)", "- Date: TODO(student)", ""]

    lines += [
        "## 2. Architecture",
        "",
        "TODO(student): describe your graph nodes, edges, state fields, and reducers.",
        "",
    ]

    lines += [
        "## 3. State schema",
        "",
        "TODO(student): list important fields and whether they are overwrite or append-only.",
        "",
        "| Field | Reducer | Why |",
        "|---|---|---|",
        "| messages / tool_results / errors / events | append | audit trail across the run |",
        "| route / evaluation_result / pending_question / proposed_action / approval | overwrite | only the current value drives routing |",
        "",
    ]

    lines += [
        "## 4. Scenario results",
        "",
        f"- Total scenarios: {metrics.total_scenarios}",
        f"- Success rate: {metrics.success_rate:.1%}",
        f"- Avg nodes visited: {metrics.avg_nodes_visited:.2f}",
        f"- Total retries: {metrics.total_retries}",
        f"- Total interrupts: {metrics.total_interrupts}",
        "",
        "| Scenario | Expected route | Actual route | Success | Retries | Interrupts |",
        "|---|---|---|---:|---:|---:|",
    ]
    for m in metrics.scenario_metrics:
        success_mark = "yes" if m.success else "no"
        lines.append(
            f"| {m.scenario_id} | {m.expected_route} | {m.actual_route or '-'} | "
            f"{success_mark} | {m.retry_count} | {m.interrupt_count} |"
        )
    lines.append("")

    lines += [
        "## 5. Failure analysis",
        "",
        "TODO(student): describe at least two failure modes you considered:",
        "",
        "1. Retry or tool failure:",
        "2. Risky action without approval:",
        "",
    ]

    lines += [
        "## 6. Persistence / recovery evidence",
        "",
        "TODO(student): explain how you used checkpointer, thread id, state history, or crash-resume.",
        "",
    ]

    lines += [
        "## 7. Extension work",
        "",
        "TODO(student): describe any extension you completed: SQLite/Postgres, time travel, "
        "fan-out/fan-in, graph diagram, tracing.",
        "",
    ]

    lines += [
        "## 8. Improvement plan",
        "",
        "TODO(student): if you had one more day, what would you productionize first?",
        "",
    ]

    return "\n".join(lines)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
