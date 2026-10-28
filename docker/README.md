# Docker helper scripts

> Build- and run-time helper scripts for the **Fredgar AI** containers, used by [`Dockerfile`](../Dockerfile) and [`docker-compose.yml`](../docker-compose.yml).

| File | Role |
|------|------|
| [`entrypoint-web.sh`](entrypoint-web.sh) | `cd /app/src`, run `migrate --noinput`, then `exec` the container command (typically gunicorn). |
| [`ci.sh`](ci.sh) | CI image entry: `ruff check`, `makemigrations --check`, `manage.py check`, `pytest` with coverage floors on selected packages. |
| [`nginx-frontend.conf`](nginx-frontend.conf) | Static UI profile: serve Vite build and proxy `/api` to the Django service. |

For end-to-end Compose usage, see the root [`README.md`](../README.md).
