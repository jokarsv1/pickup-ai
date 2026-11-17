# Pickup

An AI assistant that answers the calls you can't or don't want to take. It talks to the caller in
their language, finds out who they are and why they called, follows your instructions, and shows you
a live transcript with one-tap replies. Built for India first (Hindi, English, Hinglish and more),
as a competitor to Equal AI.

- **Android app** (`android/`): Kotlin, Jetpack Compose, call screening, guided forwarding setup,
  live call notifications, assistant chat.
- **Backend** (`backend/`): FastAPI, Postgres, Redis, a Pipecat voice agent with Claude, Sarvam
  speech, and Exotel/Plivo/Twilio telephony.

## How it works

Pickup's call screener declines unknown callers. The carrier forwards declined calls to the user's
own assistant number, where the voice agent answers. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Status

| Built and tested | Waiting on you ([docs/SETUP.md](docs/SETUP.md)) |
|---|---|
| Backend API, telephony adapters, voice pipeline, summaries, assistant chat, scheduler (14 tests) | Anthropic, Sarvam, Firebase keys |
| Android app: onboarding, screening, home, live call, detail, chat, settings, billing | Exotel account, KYC and numbers |
| Screening rules and formatting (19 JVM unit tests) | Hosting with HTTPS |
| Eval suite with 8 simulated-caller scenarios | Google Play Console, legal pages |
| Docker, docker-compose, Alembic migrations, GitHub Actions | The `pickup-ai` GitHub repo |

## Quick start

```bash
cp backend/.env.example backend/.env
```

```bash
docker compose up --build
```

The API runs on http://localhost:8000 (OpenAPI docs at `/docs`). Sign in from the app with any
Indian mobile number and code `123456`.

Run the backend tests:

```bash
cd backend && pip install ".[dev]" && python -m pytest
```

Build the Android app (Android Studio or):

```bash
cd android && ./gradlew assembleDebug
```

The debug build talks to `http://10.0.2.2:8000` (your machine, from the emulator). Change it with
`-Ppickup.apiBaseUrl=https://…`, or long-press the logo on the welcome screen.

Talk to the agent in your terminal (needs `ANTHROPIC_API_KEY`):

```bash
cd backend && python -m scripts.chat_with_agent --owner "Your Name"
```

## Docs

- [docs/SETUP.md](docs/SETUP.md): the remaining external steps, in order
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): call flow, components, API, data
- [docs/PRODUCT.md](docs/PRODUCT.md): positioning against Equal AI, UX principles, plans
- [docs/RESEARCH.md](docs/RESEARCH.md): the research behind each technical decision, with sources
