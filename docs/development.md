# Development Guide

How to run Ukinory locally and work on it day to day.

## Prerequisites

- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux (SonarQube analysis only):** Python 3 must be installed and available as `python3` to run `scripts/analyze.sh`.

> Python, Node.js, PostgreSQL and Redis don't need to be installed locally. They run inside Docker containers. Python 3 is only required on Linux if you want to run the SonarQube analysis script.

## First-time setup

### 1. Clone the repository

```bash
git clone https://github.com/xultimatex8/ukinory.git
cd ukinory
```

### 2. Environment variables

Create `.env` at the project root from the provided example.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**Linux / macOS / WSL**

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | PostgreSQL connection (used in development; `POSTGRES_HOST` is `db` inside Compose) |
| `DATABASE_URL` | Full connection string. Only used when `ENVIRONMENT=production`; in development Django uses the `POSTGRES_*` variables |
| `DJANGO_SECRET_KEY` | Django secret key |
| `ENVIRONMENT` | `production` turns off `DEBUG`, forces HTTPS and switches to `DATABASE_URL`. Anything else (or unset) is development |
| `GEMINI_API_KEY` | Gemini API key (embeddings and text generation) |
| `TMDB_API_KEY` | TMDb API key |
| `WIKIDATA_USER_AGENT` | Descriptive User-Agent sent to Wikidata (required by Wikimedia's API policy) |
| `REDIS_URL` | Redis connection string. In development Django always uses `redis://redis:6379/1`, so this only matters in production |
| `FRONTEND_URL` | Public URL of the frontend, added to the CORS and CSRF trusted origins |

#### Production-only variables

These aren't in `.env.example` and aren't needed locally.

| Variable | Purpose |
|---|---|
| `GITHUB_DISPATCH_TOKEN`, `GITHUB_REPO` | Let the backend trigger the import worker workflow on GitHub Actions |
| `GITHUB_WORKFLOW_FILE` | Workflow to dispatch (default `process-imports.yml`) |
| `GITHUB_DISPATCH_REF` | Branch to run it on (default `main`) |
| `RENDER_EXTERNAL_HOSTNAME` | Set automatically by Render; added to `ALLOWED_HOSTS` |

### 3. Start the project

```bash
docker compose up -d --build
```

This starts six containers:

| Service | What it does | Port |
|---|---|---|
| `frontend` | React + Vite dev server | 5173 |
| `backend` | Django dev server (served through Daphne, so WebSockets work) | 8000 |
| `db` | PostgreSQL + pgvector | 5432 |
| `redis` | Cache, WebSocket channel layer, RQ job queue and request pacing | 6379 |
| `rqworker` | RQ worker that processes Letterboxd import jobs | none |
| `cron` | Runs the scheduled management commands | none |

The backend also exposes `5678` for the `debugpy` debugger (attach from your IDE) and `8888` for Jupyter (see below).

The backend image is shared by `backend`, `rqworker` and `cron`. Only the command changes between them, and the last two skip the entrypoint so they don't run migrations.

Available at:

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend: [http://localhost:8000](http://localhost:8000)

> **Scheduled jobs run locally too.** The `cron` container installs the `CRONJOBS` from `settings.py`,
> including the catalog seeding, which calls TMDb, Wikidata and Gemini with your API keys.
> If you don't want that while developing, stop it with `docker compose stop cron`.
> In production the same commands run as GitHub Actions workflows, and import jobs are processed by
> the `process-imports.yml` worker instead of `rqworker`.

### 4. Migrations

The backend's entrypoint runs `migrate` and `collectstatic` every time the container starts, so
normally there's nothing to do. To run them manually:

```bash
docker compose exec backend python manage.py migrate
```

## Day-to-day workflow

Leave Docker Compose running:

```bash
docker compose up -d
```

Source code is mounted into the containers, so changes are picked up automatically:

- **React/Vite** uses Hot Module Replacement.
- **Django** restarts through the development server's autoreloader.
- **PostgreSQL** runs in its own container, with data persisted in a Docker volume.

The **RQ worker** and the **cron** container don't hot-reload. Restart them after changing code they run, or after editing `CRONJOBS`:

```bash
docker compose restart rqworker cron
```

Stop the containers (keeping the database):

```bash
docker compose down
```

Rebuild after changing dependencies or Dockerfiles:

```bash
docker compose up -d --build
```

Stop the containers and **delete all PostgreSQL data**:

```bash
docker compose down -v
```

> This also deletes the SonarQube data volumes if you have used SonarQube. Your local SonarQube configuration and analysis history will be lost.

## Jupyter Notebook

Jupyter is available inside the backend container for data analysis and experiments. It's optional.

With the services running:

```bash
docker compose exec backend jupyter notebook --ip=0.0.0.0 --port=8888 --allow-root --no-browser
```

The terminal prints a URL like `http://127.0.0.1:8888/tree?token=<generated-token>`. Open the URL printed in your terminal (the token is generated on every start). Stop Jupyter with `Ctrl+C`.

## Tests

Tests run inside the containers, the same way CI runs them.

```bash
# Backend (pytest)
docker compose exec backend pytest

# Django system checks (also run in CI)
docker compose exec backend python manage.py check
```

The frontend has a test suite, along with linting and the production build. You can run all frontend checks locally:

```bash
# Frontend tests
docker compose exec frontend npm run test:run

# Frontend lint
docker compose exec frontend npm run lint

# Frontend production build
docker compose exec frontend npm run build
```

See [Testing and CI](../README.md#testing-and-ci) for what the pipeline runs and when.

## SonarQube

Ukinory includes SonarQube Community Build for local static code analysis. The `sonarqube` service runs the server, and the `sonarscanner` service runs the analysis.

### 1. Start SonarQube

Start the SonarQube server:

```bash
docker compose up -d sonarqube
```

Open [http://localhost:9000](http://localhost:9000).

On the first login, use `admin` as both the username and password, then follow the instructions to change the default password if prompted.

### 2. Generate a SonarQube token

1. Log in to SonarQube.
2. Go to **My Account → Security**.
3. Generate a user token and copy it.

Set the `SONAR_TOKEN` environment variable in the same terminal session you will use to run the analysis.

**Windows PowerShell**

```powershell
$env:SONAR_TOKEN = "your-sonarqube-token"
```

**Linux / macOS / WSL**

```bash
export SONAR_TOKEN="your-sonarqube-token"
```

Replace `your-sonarqube-token` with your generated token. Do not commit the token to the repository.

### 3. Run the analysis

The scripts in `scripts/` run the backend tests, generate a coverage report, adjust its paths for SonarScanner, and submit the analysis to SonarQube.

**Windows — PowerShell**

Run from the repository root:

```powershell
.\scripts\analyze.ps1
```

**Linux**

Python 3 must be installed and accessible through the `python3` command. Run from the repository root:

```bash
chmod +x scripts/analyze.sh
./scripts/analyze.sh
```

### 4. View the results

When the analysis finishes, open [http://localhost:9000](http://localhost:9000) and select the Ukinory project to review the results.

The first analysis may take several minutes.