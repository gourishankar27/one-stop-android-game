# One Job server

Current functionality: `GET /health`. Gameplay and `/ws` are planned, not exposed.
The package uses a `src/` layout and Python 3.12+.

From this directory:

```bash
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
uv run uvicorn one_job.main:app --host 127.0.0.1 --port 8000
```

The checked-in `uv.lock` pins dependencies. Update it deliberately with `uv lock`
when changing `pyproject.toml`, then rerun checks. `uv sync --locked` must work on
a clean clone; do not commit `.venv/`. A pip alternative is
`python -m pip install -e '.[dev]'` in a Python 3.12 virtual environment; this
uses the declared ranges rather than the uv lock.

`uv build` produces a source distribution and wheel in ignored `dist/`.
Observed foundation results and tool versions are recorded in
[FOUNDATION_VALIDATION.md](../docs/FOUNDATION_VALIDATION.md).

`one_job.main.create_app()` creates an isolated app for tests. The health route
uses a Pydantic response model and reports liveness only. Later phases add
`domain/`, `application/`, `protocol/` and more transport routes when needed.
Those packages are deliberately absent until they contain behavior.

Run one Uvicorn worker when in-memory rooms are introduced. Multiple workers
would own different room registries. Development reload also erases rooms.

For real-phone development later, bind to a reachable private address and use
the debug transport configuration introduced in Phase 06. Phase 00 has no
Android network permission, endpoint selector or gameplay socket.
