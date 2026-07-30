# Project Rules

## Git Workflow

Use GitFlow for all development:

- `main` contains production-ready code.
- `develop` is the integration branch for upcoming releases.
- Create `feature/<name>` branches from `develop` for new capabilities.
- Create `release/<version>` branches from `develop` for release stabilization.
- Create `hotfix/<name>` branches from `main` for urgent fixes and production hardening.
- Merge hotfixes back into both `main` and `develop` when `develop` exists.
- Do not commit directly to `main` or `develop`; use pull requests.

## Commit Messages

Use the gitemoji style for commit messages:

```text
<emoji> <type>: <summary>
```

Examples:

```text
🎉 init: initialize LLMGarage
✨ feat: add GPU detection
🐛 fix: handle missing llama-server path
📝 docs: update setup guide
♻️ refactor: simplify preset storage
✅ test: cover model recommendation rules
```

Keep the summary concise, imperative, and focused on the user-visible change.
