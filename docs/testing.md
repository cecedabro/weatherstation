# Testing (read this — you write the tests)

The harness decides a task is done by running its `accept:` command and
`make check`. You write those tests. A weak test that passes without proving the
behaviour is a **failed task**, not a shortcut: it defeats the only safety the
loop has. Write tests you would be embarrassed to see pass on broken code.

## The one rule
Every test asserts a behaviour named in `SPEC.md`, with a concrete expected
value — not merely that code ran.

## Required, not optional
- **Assert on values, not truthiness.** `assert resp.status_code == 200 and
  resp.json()["accepted"] == 2`, never `assert resp.json()`.
- **One success AND one failure path per endpoint.** e.g. ingest: a good batch
  stores rows; a bad token returns 401 and stores nothing (check the DB row count).
- **Check side effects.** After ingest, query the DB and assert the exact rows.
  After an upsert of the same reading, assert the count did not grow.
- **Use real Postgres** for storage and API tests. Do not mock the database —
  mocks would hide the bugs the tests exist to catch. There is no Docker or system
  Postgres in this environment, so `backend/tests/conftest.py` starts a throwaway
  one with `pgserver` (T01/T03 create it):
  ```python
  import pgserver, pytest

  @pytest.fixture(scope="session")
  def pg_url(tmp_path_factory):
      srv = pgserver.get_server(tmp_path_factory.mktemp("pg"))
      yield srv.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
      srv.cleanup()
  ```
  Set `DATABASE_URL` from `pg_url` (and run the Alembic migration) **before** the
  app is imported. Truncate tables between tests.
- **Boundaries.** Ranges from the schema (a temp of 200°C rejected), empty
  series, unknown node, bad `step`, the 15-minute online cutoff.
- **Firmware:** `encode()` output is parsed and its fields checked against the
  contract; calibration functions checked with known input→output pairs.

## Banned (these count as not-done)
- Tests with no assertion, or only `assert True` / `assert response`.
- Asserting only that a function "doesn't raise".
- Tests that restate the implementation (asserting a mock was called) instead of
  the observable result.
- Marking a test `skip`/`xfail` to get `make check` green. If you can't make it
  pass, stop and let the harness record the failure.

## Shape
Arrange–Act–Assert, one behaviour per test, descriptive names
(`test_ingest_rejects_soil_metric_on_weather_node`). Fast: the whole suite should
run in well under the task timeout.

## A good vs bad example
```python
# BAD — passes on broken code
def test_ingest():
    r = client.post("/api/v1/readings", json=body, headers=auth)
    assert r.status_code == 200

# GOOD — proves SPEC 3.1 + 2.2
def test_ingest_stores_one_row_per_metric(db):
    r = client.post("/api/v1/readings", json={"readings": [WEATHER_BATCH]}, headers=auth)
    assert r.status_code == 200
    assert r.json() == {"accepted": 1, "rejected": []}
    rows = db.execute(select(Reading).where(Reading.node_id == "weather-main")).scalars().all()
    assert {row.metric for row in rows} == set(WEATHER_BATCH["metrics"])
    assert any(r.metric == "temp_c" and r.value == 14.2 for r in rows)
```
