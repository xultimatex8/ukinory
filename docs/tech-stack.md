# Tech Stack — Ukinory

## Overview

| Layer | Technology |
|---|---|
| Backend | Django (REST API), served with Daphne (ASGI) |
| ORM | Django ORM |
| AI / ML | Python, Gemini API (embeddings and text generation) |
| Database | PostgreSQL + pgvector |
| Cache / real-time / queue | Redis, WebSockets, RQ |
| Frontend | React (Vite) + TypeScript |
| Styling | Tailwind CSS |
| External data | TMDb (matching, posters, streaming availability), Wikidata (movie metadata) |
| Containerization | Docker Compose |
| CI/CD and scheduled jobs | GitHub Actions |
| Hosting | Render (backend), Vercel (frontend) |

## Decisions

### Backend: Django

- **Why:** authentication was the priority. Django provides registration, login, JWT issuance and password reset largely out of the box, so there's far less to hand-roll than with a minimal framework.
- Django's ORM and migrations remove the need to choose and configure a separate ORM.
- **Serving:** Daphne (ASGI) in production, so the same process handles REST and WebSockets. Locally, Compose runs the development server under `debugpy`.
- **Trade-off:** more framework than a pure API strictly needs, accepted in exchange for not building auth and admin tooling by hand.

### AI / ML: Python inside the Django project

- Python is the standard ecosystem for ML and data work.
- Keeping the recommendation code in the same project as the backend avoids a separate ML service and keeps access to the database and application logic simple.
- Recommendations combine **semantic embeddings** (content similarity) and a **collaborative filtering** (what similar users rated highly).

### Embeddings and LLM: Gemini

- Movie embeddings are generated with Gemini's embedding API and reused across all users, so there is no per-user recalculation.
- Embeddings for the films that drive a user's recommendations are computed during the import; the rest go through Gemini's batch API asynchronously. See [the import flow](letterboxd-export-import-flow.md#why-the-priority-split-matters).
- Gemini also writes the taste profile, the comparison narrative and the per-candidate recommendation justifications.
- Gemini usage is capped by daily and weekly budgets per client (synchronous embeddings, batch embeddings, generation and narratives), tracked in Redis. Narrative generation reserves its estimated cost before the call and reconciles it against the actual token usage afterwards.

### Database: PostgreSQL + pgvector

- A robust relational store for structured data (users, ratings, sessions).
- `pgvector` stores and queries movie embeddings directly in PostgreSQL, so there is no separate vector database to operate.

### Movie data: TMDb for matching, Wikidata for metadata

- Letterboxd exports contain only titles and years, so each film is matched to a TMDb id first.
- Descriptive metadata (description, runtime, directors, genres) comes from Wikidata, looked up by TMDb id and cached once per movie.
- Posters, ratings and streaming availability are fetched from TMDb at display time rather than stored.
- External calls are batched, paced and retried; see [the import flow](letterboxd-export-import-flow.md).

### Real-time and background work: WebSockets and Redis

- Paired swipe sessions and comparison rooms need both users to see each other's actions live, so they use WebSockets.
- Comparison-room sockets only broadcast "something changed" events; clients re-fetch the state.
- Redis has four roles:
  - **Channel layer** for the WebSockets, so events reach both participants even across server processes.
  - **Job queue** (RQ) for Letterboxd import jobs, processed by a worker.
  - **Request pacing** for TMDb, Wikidata and Gemini embeddings: a small Lua script hands out request slots atomically, so the minimum interval between calls holds across processes and scheduled jobs.
  - **Cache**, which also stores the daily and weekly spend counters that cap Gemini usage.

### Frontend: React + TypeScript

- Django acts as a pure API, so there's no reason to give up React; Django REST Framework + React is a well-supported combination.
- React fits the app's interactive features.
- It's a technology I already know, which keeps the focus on Ukinory's functionality rather than on learning a new framework.

### Containerization: Docker

- Docker Compose runs the whole stack with one command: frontend, backend, PostgreSQL + pgvector, Redis, an RQ worker for imports and a cron container for scheduled jobs. See [development.md](development.md).
- The backend image is shared by the backend, the RQ worker and the cron container, and runs migrations and collects static files on start.

### CI/CD and background jobs: GitHub Actions

- CI, CD and the secrets scan live in GitHub Actions. CI runs the backend tests against real PostgreSQL + pgvector and Redis services, lints and builds the frontend, and checks that the Compose stack builds and starts. Publishing a release deploys the backend to Render and the frontend to Vercel.
- Recurring maintenance (catalog seeding, embedding batch sync, cleanup of stale guests, rooms, sessions, invites and import jobs) and the import worker also run as scheduled workflows that execute Django management commands against production. This avoids paying for an always-on worker.
- **Trade-off:** GitHub's scheduler is best-effort, so short intervals like every five minutes can be delayed by several minutes, and scheduled workflows in a public repository are paused after 60 days without repository activity.