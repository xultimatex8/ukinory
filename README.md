# Ukinory

A web application for **movie taste analysis and collaborative movie discovery**, built around user-provided Letterboxd data, TMDb metadata, machine learning, and LLM-generated recommendations.

It lets users import their Letterboxd history, generate a personalized taste profile, compare their tastes with other users, and discover movies through individual or real-time paired swipe sessions.

## Main Features (MVP)

* **Guest and registered accounts** — Use Ukinory without signing up, or create an account later to permanently keep your data.
* **Letterboxd data import** — Upload your Letterboxd export and automatically match the movies with TMDb to retrieve their metadata.
* **Personal taste profile** — Analyze a user's data to generate an AI-written profile describing their movie tastes.
* **Taste comparison** — Connect two or more users and compare their movie preferences.
* **Individual movie discovery** — Browse personalized movie recommendations through a Tinder-style swipe interface.
* **Paired movie discovery** — Two users can swipe through the same recommendations in real time. When both users add a movie to their watchlist, Ukinory detects a match and "adds" it to both watchlists.
* **Machine learning recommendations** — Predict how a user might rate unwatched movies and use ratings and swipe history to improve future recommendations.
* **Watchlist export** — Export movies added through Ukinory as a Letterboxd-compatible CSV for manual import.
* **Invite links** — Generate shareable, expiring links to connect with another user for a taste comparison or paired swipe session.
* **Spanish and English** — Switch the application language.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django |
| ORM | Django ORM |
| AI / ML | Python |
| Database | PostgreSQL (+pgvector) |
| Frontend | React (Vite) + TypeScript |
| Styling | Tailwind CSS |
| Containerization | Docker |

More detail and rationale behind these decisions in [`docs/tech-stack.md`](docs/tech-stack.md).

## Documentation

- [Tech Stack and rationale](docs/tech-stack.md)
- [MVP functional requirements](docs/mvp-functional-requirements.md)
- [Data model](docs/data-model.md)

## Running the Project

### Prerequisites

- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

> Python, Node.js, and PostgreSQL do not need to be installed locally. They run inside Docker containers.

### 1. Clone the repository

```bash
git clone <REPOSITORY_URL>
cd Ukinory
```

### 2. Set up environment variables

Create the `.env` file at the project root from the provided example:

#### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

#### Linux / macOS / WSL

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
POSTGRES_DB=ukinory_db
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### 3. Run the project

Build and start all services:

```bash
docker compose up --build
```

The application consists of three Docker containers:

1. **Frontend** — React + Vite
2. **Backend** — Django
3. **Database** — PostgreSQL + pgvector

The application will be available at:

- Frontend: http://localhost:5173
- Backend: http://localhost:8000

### 4. Apply database migrations

If migrations have not been applied automatically, run:

```bash
docker compose exec backend python manage.py migrate
```

### Day-to-day development

The recommended development workflow is to leave Docker Compose running:

```bash
docker compose up
```

Source code is mounted into the containers, so changes made to the project are automatically detected:

- **React/Vite** uses Hot Module Replacement (HMR), so frontend changes are reflected automatically in the browser.
- **Django** uses its development server's autoreloader, so backend changes automatically restart the server.
- **PostgreSQL** runs continuously in its own container, with its data persisted using a Docker volume.

When you finish working, stop the containers with:

```bash
docker compose down
```

This stops and removes the containers while **preserving the PostgreSQL data** stored in the Docker volume.

If you need to rebuild the containers, for example after changing dependencies or Dockerfiles, use:

```bash
docker compose up --build
```

To stop the containers and **delete all PostgreSQL data**, use:

```bash
docker compose down -v
```
