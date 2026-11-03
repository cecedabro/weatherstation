"""Helpers for check-migrations.sh. Run inside a checkout's backend/ directory.

Data goes in and comes out only through the contract API (POST /api/v1/readings,
GET /api/v1/current and /api/v1/series), so the check works across versions
whatever the table names are.

    python migcheck.py wipe
    python migcheck.py seed <contract/samples dir>
    python migcheck.py verify
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())  # the checkout's backend/, so `app` is importable

SAMPLES = ("weather_valid.json", "soil_valid.json")
AUTH = {"Authorization": f"Bearer {os.environ.get('INGEST_TOKEN', 'migcheck-token')}"}


def wipe() -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import OperationalError

    url = make_url(os.environ["DATABASE_URL"])
    try:
        create_engine(url).connect().close()
    except OperationalError:  # database missing: create it from the server's default db
        admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    with create_engine(url).begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def seed(samples_dir: str) -> None:
    batches = [json.loads((Path(samples_dir) / name).read_text()) for name in SAMPLES]
    r = client().post("/api/v1/readings", json={"readings": batches}, headers=AUTH)
    assert r.status_code == 200 and r.json().get("accepted") == len(batches), r.text
    print(f"seeded {len(batches)} batches")


def verify() -> None:
    c = client()
    ids = {n["node_id"] for n in c.get("/api/v1/current").json()}
    assert {"weather-main", "soil-bed-3"} <= ids, f"nodes missing after upgrade: {ids}"
    params = {"node": "weather-main", "metric": "temp_c", "step": "raw",
              "from": "2026-05-01T00:00:00Z", "to": "2026-05-02T00:00:00Z"}
    r = c.get("/api/v1/series", params=params)
    assert r.status_code == 200 and "14.2" in r.text, f"reading lost after upgrade: {r.text}"
    print("data intact after upgrade")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["?"]
    {"wipe": wipe, "seed": seed, "verify": verify}[cmd](*args)
