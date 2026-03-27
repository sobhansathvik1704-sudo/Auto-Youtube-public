# YouTube AI – Automated YouTube Video Creator

An AI-powered platform that automatically generates, renders, and uploads YouTube videos from a text topic. Provide a subject, and the system writes a script, generates voiceover audio, creates visual slides, renders an MP4, and optionally uploads it straight to YouTube.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Browser                          │
│                  Next.js 14 Frontend                    │
└────────────────────┬───────────────────────────────────┘
                     │ HTTP / REST
┌────────────────────▼───────────────────────────────────┐
│              FastAPI Backend  (port 8000)               │
│   Auth · Projects · Video Jobs · Artifacts · Scripts   │
└────────┬──────────────────────────┬────────────────────┘
         │ SQLAlchemy (PostgreSQL)   │ Celery tasks via Redis
┌────────▼──────────┐     ┌─────────▼──────────────────┐
│   PostgreSQL 16   │     │   Celery Worker             │
│   (port 5432)     │     │   LLM · TTS · FFmpeg render │
└───────────────────┘     └────────────┬────────────────┘
                                       │ optional
                          ┌────────────▼────────────────┐
                          │   YouTube Data API v3       │
                          │   (OAuth 2.0 upload)        │
                          └─────────────────────────────┘
```

---

## Tech Stack

| Layer      | Technology                                  |
|------------|---------------------------------------------|
| Frontend   | Next.js 14, React, TypeScript, Tailwind CSS |
| Backend    | FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| Task Queue | Celery 5, Redis 7                           |
| Database   | PostgreSQL 16                               |
| AI / LLM   | OpenAI GPT-4o (or local fallback)           |
| TTS        | Google Cloud Text-to-Speech (or edge-tts)   |
| Video      | FFmpeg, Pillow                              |
| Storage    | Local filesystem or AWS S3                  |
| Auth       | JWT (python-jose)                           |

---

## Prerequisites

- **Docker** and **Docker Compose** v2+
- *(Optional)* **OpenAI API key** – for AI-generated scripts
- *(Optional)* **Google Cloud** project with Text-to-Speech API enabled – for real voiceover
- *(Optional)* **YouTube Data API v3** OAuth 2.0 credentials – for automatic upload

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/sobhansathvik1704-sudo/Auto-Youtube-public.git
cd Auto-Youtube-public
```

### 2. Configure environment variables

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your real credentials
nano backend/.env
```

### 3. (Optional) Add Google Cloud TTS credentials

```bash
cp /path/to/your/google-service-account.json backend/google_tts_credentials.json
# Set in backend/.env:
# GOOGLE_APPLICATION_CREDENTIALS=google_tts_credentials.json
# TTS_PROVIDER=google
```

### 4. (Optional) Add YouTube OAuth credentials

1. Create an OAuth 2.0 Client ID in the [Google Cloud Console](https://console.cloud.google.com/)
2. Download the JSON and save it as `backend/client_secrets.json`
3. Set `YOUTUBE_CLIENT_SECRETS_FILE=client_secrets.json` in `backend/.env`

### 5. Start the application

```bash
docker compose up --build -d
```

### 6. Open the app

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | – | Long random secret for JWT signing |
| `DATABASE_URL` | ✅ | – | PostgreSQL connection string |
| `REDIS_URL` | ✅ | `redis://redis:6379/0` | Redis connection |
| `LLM_PROVIDER` | ✅ | `local` | `local` or `openai` |
| `OPENAI_API_KEY` | When `LLM_PROVIDER=openai` | – | OpenAI API key |
| `TTS_PROVIDER` | ✅ | `local` | `local`, `google`, or `edge` |
| `GOOGLE_APPLICATION_CREDENTIALS` | When `TTS_PROVIDER=google` | – | Path to GCP service account JSON |
| `STORAGE_BACKEND` | ✅ | `local` | `local` or `s3` |
| `ARTIFACTS_DIR` | ✅ | `/data/artifacts` | Directory for generated files |
| `YOUTUBE_CLIENT_SECRETS_FILE` | For YouTube upload | `client_secrets.json` | OAuth client secrets path |
| `YOUTUBE_TOKEN_FILE` | For YouTube upload | `youtube_token.json` | Cached OAuth token path |
| `AWS_ACCESS_KEY_ID` | When `STORAGE_BACKEND=s3` | – | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | When `STORAGE_BACKEND=s3` | – | AWS credentials |
| `AWS_S3_BUCKET_NAME` | When `STORAGE_BACKEND=s3` | – | S3 bucket name |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Health check |
| `POST` | `/api/auth/register` | No | Register a new user |
| `POST` | `/api/auth/login` | No | Login and get JWT |
| `GET` | `/api/auth/me` | ✅ | Current user info |
| `POST` | `/api/projects` | ✅ | Create a project |
| `GET` | `/api/projects` | ✅ | List projects |
| `GET` | `/api/projects/{id}` | ✅ | Get a project |
| `PUT` | `/api/projects/{id}` | ✅ | Update a project |
| `POST` | `/api/video-jobs` | ✅ | Create a video job |
| `GET` | `/api/video-jobs` | ✅ | List video jobs |
| `GET` | `/api/video-jobs/{id}` | ✅ | Get a video job |
| `GET` | `/api/video-jobs/{id}/status` | ✅ | Get job status + events |
| `GET` | `/api/video-jobs/{id}/download` | ✅ | Get download URL |
| `GET` | `/api/video-jobs/{id}/download/file` | ✅ | Stream the video file |
| `POST` | `/api/video-jobs/{id}/upload` | ✅ | Upload to YouTube |

Interactive API documentation is available at **http://localhost:8000/docs**.

---

## Project Structure

```
Auto-Youtube-public/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # FastAPI route handlers
│   │   ├── core/               # Config, database, security, logging
│   │   ├── db/models/          # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic (LLM, TTS, render, YouTube)
│   │   └── main.py             # FastAPI application entry point
│   ├── alembic/                # Database migrations
│   ├── tests/                  # Pytest test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/                    # Next.js 14 App Router pages
│   ├── lib/                    # API client, utilities
│   └── Dockerfile
├── .github/workflows/ci.yml    # GitHub Actions CI/CD
├── docker-compose.yml
└── README.md
```

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "feat: add my feature"`
4. Push and open a Pull Request

Please make sure all CI checks pass before requesting a review.

---

## License

This project is provided as-is for educational purposes.
