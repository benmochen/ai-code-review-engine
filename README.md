# CodeReviewBot

AI-powered code review bot that automatically reviews pull requests using Claude.

## Architecture

GitHub PR → Webhook → FastAPI → Redis Queue → Worker → Claude API → PR Comments

## Tech Stack

- **API**: FastAPI (Python)
- **Database**: PostgreSQL + SQLAlchemy ORM
- **Queue**: Redis + rq (Week 3)
- **AI**: Anthropic Claude API (Week 4)
- **Frontend**: React (Week 5)
- **Deploy**: Docker + GitHub Actions (Week 6)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or Docker)

### Setup

```bash
# Clone and enter project
cd code-review-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy env template and edit
cp .env.example .env

# Create the database
createdb code_review_bot
# Or via psql: CREATE DATABASE code_review_bot;

# Run the server
uvicorn app.main:app --reload

# Visit the auto-generated API docs
# http://localhost:8000/docs
```

### Run Tests

```bash
pytest tests/ -v
```

Tests use SQLite in-memory — no PostgreSQL needed.

## API Endpoints

| Method | Endpoint                          | Description                |
|--------|-----------------------------------|----------------------------|
| GET    | /health                           | Health check               |
| POST   | /api/users/                       | Create user                |
| GET    | /api/users/                       | List users                 |
| GET    | /api/users/{id}                   | Get user                   |
| DELETE | /api/users/{id}                   | Delete user                |
| POST   | /api/repos/                       | Register repository        |
| GET    | /api/repos/                       | List repositories          |
| GET    | /api/repos/{id}                   | Get repository             |
| POST   | /api/reviews/                     | Create review              |
| GET    | /api/reviews/                     | List reviews               |
| GET    | /api/reviews/{id}                 | Get review with comments   |
| POST   | /api/reviews/{id}/comments        | Add comment to review      |
| GET    | /api/reviews/{id}/comments        | List review comments       |

## Project Roadmap

- [x] Week 1: FastAPI + PostgreSQL + CRUD
- [ ] Week 2: GitHub OAuth + Webhook listener
- [ ] Week 3: Redis queue + background workers
- [ ] Week 4: Claude API integration
- [ ] Week 5: React dashboard
- [ ] Week 6: Docker +CI/CD deployment
