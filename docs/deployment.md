# Deployment (k3s homelab)

Kustomize manifests under `deploy/`, applied by Flux from the existing homelab
repo. The agent writes the manifests here; wiring them into Flux and applying
them is the human's job (don't touch the homelab repo). Target: the backend and
Postgres run in-cluster; the public site is exposed through the existing
Cloudflare tunnel at garden.cedricschippers.dev.

## Layout (inside `deploy/`)
```
deploy/
  Makefile               # `validate` target: kustomize build | kubeconform -strict
  base/
    namespace.yaml       # namespace: weather
    backend.yaml         # Deployment + Service (ClusterIP)
    postgres.yaml        # StatefulSet + Service + Longhorn PVC
    config.yaml          # non-secret env (ConfigMap)
    ingress.yaml         # route via the Cloudflare tunnel (see note)
    kustomization.yaml
  overlays/
    prod/kustomization.yaml       # image tag, replicas, prod config
    staging/kustomization.yaml    # namespace weather-staging, seeded/throwaway DB
  secret.example.yaml    # documents required keys; real one is SOPS in the homelab repo
```

## Rules (SPEC 9)
- Backend image: `ghcr.io/<owner>/weatherstation-backend` (CI builds it; the tag
  is set in the overlay). `imagePullPolicy: IfNotPresent` in prod.
- Postgres: StatefulSet, one replica, `storageClassName: longhorn`, a sane
  resource request. Credentials from the Secret, never inline.
- Env: `DATABASE_URL`, `INGEST_TOKEN`, `ADMIN_USER`, `ADMIN_PASSWORD` — the two
  tokens/passwords and the DB password come from a Secret; everything else from
  the ConfigMap.
- Ingress / tunnel: the homelab already runs a `cloudflared` tunnel. Expose the
  backend Service to it the same way other homelab apps are exposed — prefer a
  plain `Ingress` (or the tunnel's config) that maps garden.cedricschippers.dev →
  the backend Service on its port. If unsure of the exact mechanism, write an
  `Ingress` with host `garden.cedricschippers.dev` and leave a `# TODO: confirm
  tunnel wiring` comment; the human finishes it. Note it in PROGRESS.md.
- Run as non-root, drop capabilities, read-only root FS where possible, set
  resource requests/limits, add a readiness probe on `/healthz`.
- A migration must run before the new backend serves: an init container or a Job
  that runs `alembic upgrade head`. Keep it simple and idempotent.

## Tooling note
`kubeconform` is installed in the devbox. `kustomize` is not (yet); the deploy
tasks need it on PATH. If `make -C deploy validate` fails with "kustomize: command
not found", stop and let the harness record it. That is an environment problem
for the human.

## Validate (the accept check)
`make -C deploy validate` renders every overlay with `kustomize build` and pipes
to `kubeconform -strict -ignore-missing-schemas`. That must exit 0. You are not
deploying to a live cluster in the loop — only producing valid manifests.
