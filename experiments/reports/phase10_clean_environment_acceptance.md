# Phase 10 clean-environment acceptance

Date: 2026-08-13  
Status: **accepted with documented package-index requirement**

## Isolation contract

- Source was exported from Git revision `754aa0d` using `git archive`; untracked
  files, the working-tree `.venv`, local reports and model artifacts were absent.
- A new venv was created under a random `/tmp/servicepilot-clean.*` directory
  using CPython 3.11.15.
- The package and `.[dev]` dependencies were installed from `pyproject.toml`.
- The editable package was rebound to the archived source and its import path was
  verified inside that snapshot.
- No Docker, GPU, model weights, paid API or `deer-flow/.env` was used.

## Results

| Gate | Result |
| --- | ---: |
| Package build and editable install | pass |
| Full pytest suite | 261 passed |
| Ruff over `src`, `tests`, and `scripts` | pass |
| Four-case CPU demo | 4/4 expected outcomes |
| Evidence catalog validation | 11/11 entries present |
| Trace Viewer generated | pass |

Source archive SHA256:
`095f23f2620656bd7091bdc1190a0511a73380228f6db517dedc1fea1edb7ad6`

Installed environment freeze SHA256:
`4ad635eea468f4263c2cafdc6e2ba898d395883e6061283cc2e895dcc1031d62`

Generated demo bundle SHA256:
`92a4f524dd9a2985aec5fcc73ee4dcd919689fd27d6ec7412c42b5bd141f914b`

Generated evidence-index SHA256:
`9b837ad3679c40525e5a33f2518e91ba749703aa0afccb04fb0fe07a82a4ea21`

## Failure discovered and remediated

The first clean run passed all tests but failed the documented Ruff gate with
104 historical import/format findings. A repository-wide Ruff baseline was
applied mechanically, followed by a full 261-test regression. A second archived
snapshot then passed Ruff and every quick-start gate.

The sandboxed dependency install initially failed because PyPI access was
blocked. The identical install succeeded when network access was explicitly
allowed. Therefore the README now states that first installation requires a
configured package index or a separately supplied wheelhouse.

The host also lacked a `python3.11` command on `PATH`; the accepted run used an
explicit Python 3.11 interpreter path. The README now documents this supported
alternative.
