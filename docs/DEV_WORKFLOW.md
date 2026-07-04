# Development Workflow

## Roles

- Shawn: product owner and final reviewer.
- ChatGPT: planning, review, prompts, and release reasoning.
- Codex: implementation and test execution.
- GitHub: source of truth for code, reviews, pull requests, releases, and tags.

## Standard Flow

Use this flow for normal development unless Shawn explicitly chooses a different release path:

```powershell
git status
git checkout main
git pull
git checkout -b feature/short-description
```

Then implement the change.

```powershell
python -m pytest
python scripts/smoke_check.py
streamlit run app.py
git diff
git add <changed-files>
git commit -m "Short imperative summary"
git push
```

After review, merge to `main`, then tag the release only when Shawn explicitly approves the release.

## Manual Streamlit Check

Before release, open the Streamlit app and verify:

- Dashboard opens.
- Library opens.
- Paper Detail opens.
- Reader Workspace opens.
- Settings opens.

Do not commit, push, merge, or tag release work until the review decision is clear.
