"""Run the site locally with fake data: throwaway Postgres, migration, seed, server.

Usage: make dev   (serves on http://0.0.0.0:8000; data kept in backend/.devdb)
Re-running is safe: seeding is idempotent and refreshes timestamps to "now".
"""

import math
import os
import random
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pgserver
import uvicorn

BACKEND = Path(__file__).resolve().parents[1]
TOKEN = "dev-token"


def _batch(
    node_id: str, node_type: str, ts: datetime, battery: float | None, metrics: dict
) -> dict:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fw": "1.0.0",
        "battery_v": battery,
        "rssi_dbm": -60 if node_type == "weather" else -78,
        "metrics": metrics,
    }


def fake_readings(now: datetime) -> list[dict]:
    rng = random.Random(42)
    now = now.replace(second=0, microsecond=0)
    out: list[dict] = []
    # weather-main: every 30 min for 7 days, online right now
    for i in range(7 * 48, -1, -1):
        ts = now - timedelta(minutes=30 * i)
        hour = ts.hour + ts.minute / 60
        out.append(
            _batch(
                "weather-main",
                "weather",
                ts,
                None,
                {
                    "temp_c": round(
                        12 + 6 * math.sin((hour - 9) / 24 * 2 * math.pi) + rng.uniform(-0.5, 0.5), 1
                    ),
                    "humidity_pct": round(
                        70 - 15 * math.sin((hour - 9) / 24 * 2 * math.pi) + rng.uniform(-2, 2), 0
                    ),
                    "pressure_hpa": round(1013 + rng.uniform(-3, 3), 1),
                    "rain_mm": round(rng.choice([0, 0, 0, 0, 0.2, 0.4]), 1),
                    "wind_speed_ms": round(abs(rng.gauss(3, 1.5)), 1),
                    "wind_dir_deg": rng.randrange(0, 360, 5),
                },
            )
        )
    # soil-bed-3: hourly, online, healthy battery
    for i in range(7 * 24, -1, -1):
        ts = now - timedelta(minutes=60 * i + 5)
        out.append(
            _batch(
                "soil-bed-3",
                "soil",
                ts,
                3.92,
                {
                    "soil_moisture_pct": round(38 + 8 * math.sin(i / 11) + rng.uniform(-1, 1), 1),
                    "soil_temp_c": round(11 + rng.uniform(-1, 1), 1),
                },
            )
        )
    # soil-bed-7: low battery and silent for 3 hours (shows the admin warnings)
    for i in range(7 * 24, 2, -1):
        ts = now - timedelta(minutes=60 * i + 20)
        out.append(
            _batch(
                "soil-bed-7",
                "soil",
                ts,
                3.3,
                {
                    "soil_moisture_pct": round(30 + 5 * math.sin(i / 7), 1),
                    "soil_temp_c": round(10.5 + rng.uniform(-1, 1), 1),
                },
            )
        )
    return out


def main() -> int:
    server = pgserver.get_server(BACKEND / ".devdb")
    os.environ["DATABASE_URL"] = server.get_uri().replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
    os.environ.setdefault("INGEST_TOKEN", TOKEN)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True)

    sys.path.insert(0, str(BACKEND))
    from fastapi.testclient import TestClient

    from app.main import app

    readings = fake_readings(datetime.now(UTC))
    client = TestClient(app)
    for start in range(0, len(readings), 500):
        resp = client.post(
            "/api/v1/readings",
            json={"readings": readings[start : start + 500]},
            headers={"Authorization": f"Bearer {os.environ['INGEST_TOKEN']}"},
        )
        resp.raise_for_status()
        body = resp.json()
        if body["rejected"]:
            print("seed rejected:", body["rejected"][:3], file=sys.stderr)
            return 1
    print(f"seeded {len(readings)} readings; admin login: admin / admin")
    uvicorn.run(app, host="0.0.0.0", port=8000)  # noqa: S104
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
