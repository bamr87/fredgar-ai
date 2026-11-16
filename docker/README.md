# Docker helper scripts

> Build- and run-time helper scripts for the **Fredgar AI** containers, used by [`Dockerfile`](../Dockerfile) and [`docker-compose.yml`](../docker-compose.yml).

| File | Role |
|------|------|
| [`entrypoint-web.sh`](entrypoint-web.sh) | `cd /app/src`, run `migrate --noinput`, then `exec` the container command (typically gunicorn). |
| [`ci.sh`](ci.sh) | CI image entry: `ruff check`, `makemigrations --check`, `manage.py check`, `pytest` with the 50% coverage floor over every app (`warehouse`, `config`, `sec_edgar`, `public_data`, `api`, `enrichment`), the same flags as `ci.yml` and `make test`. |
| [`nginx-frontend.conf`](nginx-frontend.conf) | Static UI profile: serve the Vite build on container port 8080 and proxy `/api` to the Django service. |

The static UI image ([`Dockerfile.frontend`](../Dockerfile.frontend)) runs nginx as the unprivileged user (uid 101) from `nginxinc/nginx-unprivileged:1-alpine`, so it listens on container port **8080**, not 80. Compose publishes it on `127.0.0.1:${FREDGAR_FRONTEND_PROD_PORT:-8080}`, and its `HEALTHCHECK` fetches `/` with `wget`. Anything that maps the container port itself, such as the hub's generated compose override, must target 8080.

For end-to-end Compose usage, see the root [`README.md`](../README.md).
