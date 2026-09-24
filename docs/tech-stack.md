# Tech Stack — Ukinory

## Final Decision

| Layer | Technology |
|---|---|
| Backend | Django |
| ORM | Django ORM |
| AI / ML | Python |
| Database | PostgreSQL (+pgvector) |
| Frontend | React (Vite) + TypeScript |
| Styling | Tailwind CSS |
| Containerization | Docker |

## Rationale

### Backend: Django

- The priority was minimizing custom infrastructure work around authentication in particular, plus general concern that a minimal framework would mean assembling too many pieces by hand as the project grew.
- Django provides registration, login, JWT issuance, and password reset largely out of the box — far less to hand-roll than assembling JWT + password hashing manually.
- Django's ORM and migration system remove the need to choose/configure a separate ORM.
- Django also provides an administration interface, which is useful for inspecting and managing CineSync's data during development.

### AI / ML: Python

- Python is the standard ecosystem for AI and machine learning, with libraries such as scikit-learn, PyTorch and sentence-transformers.
- Ukinory's recommendation system, embeddings and collaborative filtering can therefore be developed directly in the same language as the backend without introducing a separate ML service.
- Keeping the AI/ML code within the Django project also simplifies development and communication with the database and application logic.

### Frontend: React

- Since Django serves as a pure API in this setup, there's no reason to give up React. Django REST Framework + React is a common, well-supported combination.
- React is already a technology I know, which reduces the learning curve and allows development to move faster.
- React is also a good fit for the app's interactive features: animated swipe cards, live partner status, match notifications, and dynamic views.
- Using a technology already familiar to me helps keep the project focused on implementing Ukinory's functionality rather than learning a new frontend framework.

### Database: PostgreSQL

- A robust relational store for Ukinory's structured data.
- `pgvector` stores and queries movie synopsis embeddings directly in PostgreSQL, avoiding a separate vector database.

### Containerization: Docker

- Containerizing the Django backend, the React frontend, and PostgreSQL keeps the environment reproducible as the number of moving parts grows.