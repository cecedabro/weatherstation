# Build and run the image locally

How to try the production image on your own machine (Mac with Docker Desktop) before it
goes through CI and onto the cluster. All commands run from the repo root.

## 1. Build

```bash
docker build -t weatherstation:local .
```

The first build downloads the base images and the Python dependencies; after that, only
changed layers are rebuilt. A change to `backend/pyproject.toml` or `backend/uv.lock`
reinstalls the dependencies, a change to the code only copies the code.

The cluster runs amd64. On an Apple Silicon Mac this build is arm64, which is fine for
testing. To build exactly what the cluster gets (slower, emulated):

```bash
docker build --platform linux/amd64 -t weatherstation:local-amd64 .
```

## 2. Start a database

The app needs Postgres. Put both containers on one Docker network so the app can reach
the database by its container name:

```bash
docker network create ws-test
```

```bash
docker run -d --name ws-db --network ws-test -e POSTGRES_USER=weather -e POSTGRES_PASSWORD=weather -e POSTGRES_DB=weather postgres:16
```

## 3. Create the tables

The same image runs the migrations (on the cluster this is the initContainer):

```bash
docker run --rm --network ws-test -e DATABASE_URL=postgresql+psycopg://weather:weather@ws-db:5432/weather weatherstation:local alembic upgrade head
```

If it says it cannot connect, Postgres is still starting; wait a few seconds and run it again.

## 4. Run the app

`--read-only --tmpfs /tmp` copies the cluster's setup (read-only root filesystem, only
`/tmp` writable), so you find out here if something tries to write elsewhere.

```bash
docker run -d --name ws-app --network ws-test --read-only --tmpfs /tmp -p 8000:8000 -e DATABASE_URL=postgresql+psycopg://weather:weather@ws-db:5432/weather -e INGEST_TOKEN=test-token weatherstation:local
```

Open http://localhost:8000. Logs: `docker logs -f ws-app`.

## 5. Check it

```bash
curl -s localhost:8000/healthz && curl -s localhost:8000/readyz
```

Send a sample reading (the API takes a `readings` array, so the sample is wrapped first):

```bash
python3 -c 'import json; print(json.dumps({"readings": [json.load(open("contract/samples/weather_valid.json"))]}))' | curl -s -X POST -H 'Authorization: Bearer test-token' -H 'Content-Type: application/json' --data @- localhost:8000/api/v1/readings
```

It answers `{"accepted":1,"rejected":[]}`, and the reading shows up on the site and at
http://localhost:8000/api/v1/current.

Production mode refuses default secrets. To see that guard work:

```bash
docker run --rm -e APP_ENV=production weatherstation:local python -c "from app.main import create_app; create_app()"
```

It should stop with `APP_ENV=production but INGEST_TOKEN has its development default`.

## 6. After a code change

```bash
docker rm -f ws-app && docker build -t weatherstation:local . && docker run -d --name ws-app --network ws-test --read-only --tmpfs /tmp -p 8000:8000 -e DATABASE_URL=postgresql+psycopg://weather:weather@ws-db:5432/weather -e INGEST_TOKEN=test-token weatherstation:local
```

Add the migration step (3) again if you changed `backend/alembic/`.

## 7. Clean up

```bash
docker rm -f ws-app ws-db && docker network rm ws-test
```

The database lives only in the `ws-db` container, so this also deletes the test data.
