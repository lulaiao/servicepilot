# GitHub publication

## Repository creation

Create an empty GitHub repository named `servicepilot`. Do not initialize it
with a README, license or `.gitignore`; those files already exist locally.

After replacing `<OWNER>` with the GitHub account or organization:

```bash
cd /data/ssd1/lla/servicepilot
git remote add origin git@github.com:<OWNER>/servicepilot.git
git push -u origin master
```

If the GitHub default branch should be `main`, rename the local branch only
before the first push:

```bash
git branch -m master main
git push -u origin main
```

Do not run both alternatives. Verify the exact destination with
`git remote -v` before pushing.

## GitHub settings after first push

1. Enable private vulnerability reporting and record the resulting contact path
   in `SECURITY.md`.
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
