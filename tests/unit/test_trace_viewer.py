from servicepilot.delivery import render_trace_viewer


def test_trace_viewer_escapes_untrusted_trace_content() -> None:
    html = render_trace_viewer(
        [
            {
                "title": "unsafe <title>",
                "description": "<script>alert(1)</script>",
                "scenario_id": "scenario-1",
                "expected_demo_outcome": True,
                "judge": {
                    "task_success": True,
                    "false_success": False,
                    "failure_reasons": [],
                },
                "trajectory": {
                    "events": [
                        {
                            "step": 0,
                            "role": "user",
                            "kind": "message",
                            "content": "<img src=x onerror=alert(1)>",
                            "tool_name": None,
                        }
                    ]
                },
            }
        ]
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
