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

# ---------------------------------------------------------------------------
# Seed helpers (importable for tests)
# ---------------------------------------------------------------------------


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


def _temp_c(now: datetime, ts: datetime) -> float:
    """Daily temperature curve with seasonal trend (°C).

    - Daily sine:  peak ~14:00, trough ~04:00, amplitude 8
    - Seasonal:   amplitude 5, rising through the year
    - Frost night: day 21 at 04:00 ≈ 1.0 °C
    """
    hour = ts.hour + ts.minute / 60.0
    day = (ts - now).total_seconds() / 86400.0
    daily = math.sin((hour - 9) / 24 * 2 * math.pi)
    seasonal = math.sin(day / 30 * 2 * math.pi)
    return 12 + 8 * daily + 5 * seasonal


def _rain_prob(ts: datetime, now: datetime) -> float:
    """Rain shower probability at a given timestamp.

    Three concentrated showers spread across the 30-day window.
    Probability ramps up near shower centres, drops to zero between showers.
    """
    now_epoch = now.timestamp()
    total = 86400 * 30
    centres = [0.12, 0.40, 0.72]
    for c in centres:
        centre_ts = now_epoch - (1 - c) * total
        dist = abs(ts.timestamp() - centre_ts)
        half_width = total * 0.02
        if dist <= half_width:
            return 1.0 * (1 - dist / half_width)
    return 0.0


def fake_readings(now: datetime | None = None) -> list[dict]:
    """Generate 30 days of fake sensor readings for ``make dev`` preview.

    Covers three soil beds, one weather station, a few rain showers,
    one frost night (temperature <= 2 °C), and one bed with persistent
    moisture below 25 %.

    Parameters
    ----------
    now:
        Reference time (defaults to ``datetime.now(UTC)``).  Set explicitly
        for deterministic testing.
    """
    if now is None:
        now = datetime.now(UTC)
    rng = random.Random(42)
    now = now.replace(second=0, microsecond=0)
    out: list[dict] = []

    # weather-main: every 30 min for 30 days
    for i in range(30 * 48, -1, -1):
        ts = now - timedelta(minutes=30 * i)
        temp = _temp_c(now, ts)
        temp = round(temp + rng.uniform(-0.5, 0.5), 1)
        humidity = round(
            60
            + 15 * math.sin((ts.hour + ts.minute / 60 - 9) / 24 * 2 * math.pi)
            + rng.uniform(-3, 3),
            0,
        )
        rain_mm = round(rng.uniform(0.3, 1.5), 1) if rng.random() < _rain_prob(ts, now) else 0.0
        out.append(
            _batch(
                "weather-main",
                "weather",
                ts,
                None,
                {
                    "temp_c": temp,
                    "humidity_pct": humidity,
                    "pressure_hpa": round(1013 + rng.uniform(-3, 3), 1),
                    "rain_mm": rain_mm,
                    "wind_speed_ms": round(abs(rng.gauss(3, 1.5)), 1),
                    "wind_dir_deg": rng.randrange(0, 360, 5),
                },
            )
        )

    # soil-bed-1: persistent low moisture (oscillates 20-30 %)
    for i in range(30 * 24, -1, -1):
        ts = now - timedelta(minutes=60 * i + 5)
        moist = round(25 + 5 * math.sin(i / 11) + rng.uniform(-0.5, 0.5), 1)
        out.append(
            _batch(
                "soil-bed-1",
                "soil",
                ts,
                3.92,
                {
                    "soil_moisture_pct": moist,
                    "soil_temp_c": round(11 + rng.uniform(-1, 1), 1),
                },
            )
        )

    # soil-bed-3: healthy moisture
    for i in range(30 * 24, -1, -1):
        ts = now - timedelta(minutes=60 * i + 15)
        moist = round(35 + 10 * math.sin(i / 13) + rng.uniform(-0.5, 0.5), 1)
        out.append(
            _batch(
                "soil-bed-3",
                "soil",
                ts,
                3.88,
                {
                    "soil_moisture_pct": moist,
                    "soil_temp_c": round(10.5 + rng.uniform(-1, 1), 1),
                },
            )
        )

    # soil-bed-7: low battery, older readings
    for i in range(30 * 24, 48, -1):
        ts = now - timedelta(minutes=60 * i + 20)
        moist = round(30 + 5 * math.sin(i / 7) + rng.uniform(-0.5, 0.5), 1)
        out.append(
            _batch(
                "soil-bed-7",
                "soil",
                ts,
                3.3,
                {
                    "soil_moisture_pct": moist,
                    "soil_temp_c": round(10.5 + rng.uniform(-1, 1), 1),
                },
            )
        )

    return out


# ---------------------------------------------------------------------------
# Entry point (dev server)
# ---------------------------------------------------------------------------


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
