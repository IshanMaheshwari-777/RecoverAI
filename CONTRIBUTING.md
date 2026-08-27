# Contributing

## Setup

```bash
make setup          # venv + editable install + dashboard build
pre-commit install
```

## The loop

```bash
make check          # ruff + mypy + pytest — everything CI runs
make fmt            # autofix + format
make demo           # run the pipeline and open the dashboard
```

## Layout & rules

The package is hexagonal. Dependencies point **inwards** only:

```
api / cli  →  services  →  ports  ←  adapters
                    ↘  domain  ↙
```

- **`domain/`** is pure — no I/O, no vendor SDKs, no `datetime.now()` in
  constructors. Value objects are frozen.
- **`services/`** depend on `ports` (typing.Protocol), never on `adapters` or
  a vendor SDK. They receive ports via their constructor.
- **`adapters/`** are the only place `razorpay` / `anthropic` may be imported.
  They translate vendor errors into `domain.errors` types.
- New external calls get a **port** and at least a real adapter + a test
  double.

## Tests

- `tests/unit` — one component, no I/O.
- `tests/integration` — several layers together, still no network (fakes).
- `tests/e2e` — the CLI via Typer's runner.
- Mark anything that hits a real API `@pytest.mark.live` (not run in CI).

Coverage floor is 90%. Keep it there.
