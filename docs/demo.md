# Local demo and Trace Viewer

Run from the repository root with the Python 3.11 development environment:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase10_demo.py \
  --code-revision "$(git rev-parse --short HEAD)"
```

Outputs:

- `artifacts/demo/phase10_demo.json`: Judge results and trajectories;
- `artifacts/demo/phase10_demo.jsonl`: one trajectory per line;
- `artifacts/demo/trace_viewer.html`: dependency-free local viewer.

The four demonstrations are acceptance assertions, not cherry-picked screenshots:

1. a partial refund uses preview, confirmation and execute;
2. a transient preview failure is retried and produces exactly one refund;
3. a user rejects cancellation confirmation and no write occurs;
4. an intentionally impossible expected state converts an Agent success claim
   into `FALSE_SUCCESS` using repository state outside the Agent.

The HTML renderer escapes message, tool and result content. It performs no
network requests and has no tool-execution capability.
