# Deployment (k3s homelab)

The site runs on Cédric's k3s cluster, deployed by Flux from the **homelab** repo.
This repo builds the image and keeps *draft* manifests in `deploy/`; the homelab
chat copies them into `homelab/apps/weatherstation/` and adds the namespace's
NetworkPolicy and ExternalSecrets. You never touch the cluster or the homelab repo.

## How a change reaches the cluster
1. A PR is merged into `main`.
2. `.github/workflows/release.yml` runs `make check`, computes the next version
   (`backend/scripts/next_version.py`), builds and pushes
   `ghcr.io/cecedabro/weatherstation:X.Y.Z` and `:sha-<short>`, then pushes the git
   tag `vX.Y.Z`. All in one workflow: tags pushed with `GITHUB_TOKEN` do not trigger
   other workflows.
3. Flux image automation sees the new `X.Y.Z` tag and rolls it out.

## The image (`Dockerfile` at the repo root)
- Build context is the repo root, because the app reads `../contract/`.
- Multi-stage: a builder stage installs deps with `uv sync --frozen --no-dev` into
  `/app/.venv`; the runtime stage is `python:3.11-slim` (pin the minor tag, e.g.
  `python:3.11.11-slim`), no build tools.
- Layout in the image: `backend/` → `/app`, `contract/` → `/contract` (so
  `app/schema.py`'s `parents[2]` finds it). `WORKDIR /app`. Add `/app/.venv/bin` to `PATH`.
- `USER 10001`, `EXPOSE 8000`,
  `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]`.
- `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`. Nothing may write outside `/tmp`.
- Migrations: the same image runs `alembic upgrade head` (from `/app`) as an initContainer.
- `.dockerignore` keeps out `.git`, `.agent`, `.venv`, `.devdb`, caches, `tests`, `node_modules`.
- Lint with `uvx --from hadolint-py hadolint Dockerfile`. There is no Docker in the
  devbox, so you cannot build or run the image; CI does that.

## Migrations must be safe to auto-deploy
Every merge deploys, with one replica and `Recreate`: if a migration fails, the old
pod is already gone and the site is down until a fix is released. So migrations are
idempotent and backward-compatible (add columns/tables; never drop or rename in the
same release that stops using them), and each new migration gets a test that runs
`alembic upgrade head` on an empty and on an existing database.

The check that enforces this is human-owned: `tests/ci/check-migrations.sh`, run by
`make migcheck`, `make check` and `.github/workflows/migrations.yml`.

## Runtime facts (agreed with the homelab side, do not change)
| What | Value |
| --- | --- |
| Port | container 8000, Service `weatherstation` port 80 |
| Probes | liveness `GET /healthz`, readiness `GET /readyz` |
| Env (Secret `weatherstation-app`) | `DATABASE_URL`, `INGEST_TOKEN`, `ADMIN_USER`, `ADMIN_PASSWORD` |
| Env (plain) | `APP_ENV=production` |
| DB Secret `weatherstation-db` | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| DB host | Service `weatherstation-db:5432` |
| Resources | app 25m / 128Mi request, 256Mi limit; Postgres 50m / 256Mi, 512Mi limit |
| Security | runAsNonRoot, uid 10001, readOnlyRootFilesystem, drop ALL caps, seccomp RuntimeDefault, emptyDir on `/tmp` |
| Rollout | replicas 1, strategy `Recreate` (migrations must not run twice at once) |
| Storage | Postgres PVC 5Gi, `storageClassName: longhorn` |
| Placement | avoid node `k3s-gpu-01` (node affinity `NotIn`) |

`DATABASE_URL` is composed in the cluster from the DB secret; the app only reads
the one string. Public hostname: `weatherstation.cedricschippers.dev` via the
Cloudflare tunnel (configured in the Cloudflare dashboard, so no Ingress object).

## Layout (inside `deploy/`)
```
deploy/
  Makefile             # validate: kustomize build . | kubeconform -strict -summary
  kustomization.yaml   # namespace: weatherstation; lists the files below
  namespace.yaml
  app.yaml             # Deployment (initContainers: wait-for-db, migrate) + Service
  postgres.yaml        # StatefulSet + headless/ClusterIP Service + volumeClaimTemplate
  secret.example.yaml  # documents keys with REPLACE_ME values; NOT in kustomization
```
The image line in `app.yaml` is `ghcr.io/cecedabro/weatherstation:0.1.0` with the
marker comment `# {"$imagepolicy": "flux-system:weatherstation"}`.

## Validate (the accept check)
`make -C deploy validate` must exit 0. `kustomize` and `kubeconform` are installed.
Workflows are linted with `uvx --from actionlint-py actionlint`.
