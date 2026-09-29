# Contributing to ADDA AI

Thanks for helping with this hackathon project. Small, tested pull requests are easiest to review and merge.

The repository is currently unlicensed. You may propose changes through GitHub, but do not assume the code is licensed for reuse or redistribution elsewhere.

## Pick a task

- Look through [open issues](https://github.com/pesanish5-bot/ADDA-AI/issues), especially those labeled `good first issue` or `help wanted`. If none fit, open an issue describing your proposed change.
- For a larger feature or a change to the API, graph, dependencies or deployment, discuss the approach in an issue first. A maintainer will coordinate shared files and demo priorities.
- Documentation, tests, accessibility and reproducible bug fixes are welcome. Do not claim a feature is live or deployed unless it has been verified.

The dated [team plan](docs/TASK_PLAN.md) records the original hackathon roles. External contributors should use the issue and pull-request process here rather than assuming a teammate role. [PROJECT_STATUS.md](PROJECT_STATUS.md) describes the current implementation and limits.

## Run locally

Fork the repository, clone your fork, and create a descriptive branch. Follow the [README setup instructions](README.md#run-locally) using Node.js 22+ and Python 3.13+. The default demo and document flow do not require paid API keys or AWS credentials. Copy the example environment files as instructed; never commit `.env`, `.env.local`, credentials, uploaded documents or other private data.

The frontend is in `apps/web`; the FastAPI application and tests are in `services/api`. [Architecture](docs/ARCHITECTURE.md) has more context. If setup fails, open an issue with your OS, versions, command and sanitized error output. Do not include tokens or secrets.

## Check your change

From the repository root, with the Python environment set up:

```powershell
Push-Location services/api
..\..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
Push-Location apps/web
npm.cmd run typecheck
npm.cmd run build
Pop-Location
```

On macOS/Linux, use `.venv/bin/python` and `npm`. Add or update relevant tests when behavior changes. If you cannot run a check, say so in the pull request and explain why. The same backend tests, typecheck and build run in CI for pull requests.

## Open a pull request

1. Push your branch to your fork and open a pull request against `main`.
2. Describe the problem, your solution, and how you tested it. Link the related issue if there is one. Include screenshots for visible UI changes.
3. Keep unrelated changes in separate pull requests. Avoid changing generated files or dependency locks unless the change requires it.
4. Respond to review feedback. A maintainer will merge after review and passing checks; passing CI alone does not guarantee a merge during a time-boxed demo.

Keep demo fixtures clearly labeled, treat uploaded documents and web sources as untrusted, and never execute generated code. See the [code of conduct](CODE_OF_CONDUCT.md) for community expectations.
