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
| Database | PostgreSQL |
| Frontend | React (Vite) + TypeScript |
| Styling | Tailwind CSS |
| Containerization | Docker |


## Documentation
