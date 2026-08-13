# GitHub publication

## Repository creation

The selected public repository is
`https://github.com/lulaiao/servicepilot`. It was created empty, without a
generated README, license or `.gitignore`.

```bash
cd /data/ssd1/lla/servicepilot
git branch -m master main
git remote add origin git@github.com:lulaiao/servicepilot.git
git remote -v
git push -u origin main
```

Verify the exact destination with `git remote -v` before pushing.

## GitHub settings after first push

1. Enable private vulnerability reporting; `SECURITY.md` already points to the
   repository's private advisory form.
2. Confirm the `quality` workflow passes for Python 3.11 and 3.12.
3. Protect the default branch and require both matrix checks before merging.
4. Enable Dependabot security updates.
5. Add repository topics such as `agent-harness`, `mcp`, `llm-evaluation`,
   `multi-agent`, and `local-first`.
6. Do not create a release tag until the remote workflow passes on the exact
   candidate revision.

The workflow grants only `contents: read`, does not receive repository secrets,
and runs CPU-only deterministic checks. Model/GPU experiments remain excluded
from hosted CI because their weights, hardware and sealed-evaluation contracts
are not part of the clean-source acceptance boundary.
