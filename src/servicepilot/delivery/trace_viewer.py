"""Render a dependency-free, self-contained HTML trace viewer."""

import html
import json
from collections.abc import Sequence
from typing import Any


def render_trace_viewer(demos: Sequence[dict[str, Any]]) -> str:
    cards = []
    for demo in demos:
        judge = demo["judge"]
        status = "PASS" if demo["expected_demo_outcome"] else "FAIL"
        events = []
        for event in demo["trajectory"]["events"]:
            details = ""
            if event.get("tool_name"):
                result = html.escape(json.dumps(event.get("result"), ensure_ascii=False, indent=2))
                details = (
                    f'<div class="tool">tool: {html.escape(event["tool_name"])}'
                    f"<pre>{result}</pre></div>"
                )
            events.append(
                f'<li class="{html.escape(event["role"])}"><b>{event["step"]} · '
                f"{html.escape(event['role'])} · {html.escape(event['kind'])}</b>"
                f"<p>{html.escape(event['content'])}</p>{details}</li>"
            )
        failures = ", ".join(judge["failure_reasons"]) or "none"
        cards.append(
            f"<section><h2>{html.escape(demo['title'])} <span>{status}</span></h2>"
            f'<p class="summary">{html.escape(demo["description"])}</p>'
            f'<div class="metrics">scenario={html.escape(demo["scenario_id"])} · '
            f"task_success={str(judge['task_success']).lower()} · "
            f"false_success={str(judge['false_success']).lower()} · "
            f"failures={html.escape(failures)}</div><ol>{''.join(events)}</ol></section>"
        )
    body = "".join(cards)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>ServicePilot Trace Viewer</title><style>
body{{font:15px system-ui,sans-serif;margin:0;background:#0b1020;color:#e5e7eb}}
main{{max-width:1100px;margin:auto;padding:32px}}h1{{margin-bottom:4px}}
section{{background:#151c30;border:1px solid #2b3655;border-radius:12px;
padding:20px;margin:20px 0}}h2 span{{font-size:12px;background:#14532d;
padding:4px 8px;border-radius:12px}}.summary,.metrics{{color:#aab4ca}}
ol{{padding-left:24px}}li{{margin:10px 0;padding:12px;border-left:4px solid #64748b;
background:#10172a}}
li.user{{border-color:#38bdf8}}li.assistant{{border-color:#a78bfa}}li.tool{{border-color:#f59e0b}}
p{{white-space:pre-wrap}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#070b14;
padding:10px;border-radius:6px}}
</style></head><body><main><h1>ServicePilot Trace Viewer</h1>
<p>Authoritative-state evaluation · deterministic Judge · escaped local evidence</p>
{body}</main></body></html>
"""
