# Pickup

An AI assistant that answers the calls you can't or don't want to take. It talks to the caller in
their language, finds out who they are and why they called, follows your instructions, and shows you
a live transcript with one-tap replies. Built for India first (Hindi, English, Hinglish and more),
as a competitor to Equal AI.

- **Android app** (`android/`): Kotlin, Jetpack Compose, call screening, guided forwarding setup,
  live call notifications, assistant chat.
- **iPhone app** (`ios/`): SwiftUI, the same screens; calls you decline or miss go to the assistant
  (iPhone apps can't screen calls), push through APNs, installed from TestFlight (or a free sideloaded preview).
- **Backend** (`backend/`): FastAPI, a Pipecat voice agent with Claude Haiku 5.5, Sarvam speech,
  Exotel/Plivo/Twilio telephony, FCM and APNs push. Runs on Fly.io.

## How it works

On Android, Pickup's call screener declines unknown callers; on iPhone you decline them (or turn on
Silence Unknown Callers). The carrier forwards declined calls to the user's own assistant number,
where the voice agent answers. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Try it

- **Download page:** https://pickup-ai-i6v0t.fly.dev (Android APK; iPhone preview at /install/iphone; TestFlight link once set up).
- **Your to-do list:** [docs/guides/CHECKLIST.md](docs/guides/CHECKLIST.md). iPhone: [docs/guides/IPHONE.md](docs/guides/IPHONE.md).
- **Security review:** [docs/SECURITY.md](docs/SECURITY.md).

## Status

| Built and tested | Waiting on you |
|---|---|
| Backend: API, telephony adapters, voice pipeline, summaries, chat, scheduler, push (20 tests) | Exotel account, KYC and numbers |
| Android app; APK built by CI and published on the server; emulator screenshot tour | Google Play Console (public launch, billing) |
| iPhone app; simulator build, unit tests and screenshot tour in CI | Apple Developer account (TestFlight, push) |
| 9 simulated-caller evals (all checks pass on Haiku 5.5); latency and cost probe | Firebase Blaze + SMS sign-in at launch |
| Server live on Fly.io with keys checked; security fixes ([SECURITY.md](docs/SECURITY.md)) | Make the GitHub repository private |

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

- [docs/guides/START-HERE.md](docs/guides/START-HERE.md): browser-only setup, step by step
- [docs/SETUP.md](docs/SETUP.md): the remaining external steps, in order (developer version)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): call flow, components, API, data
- [docs/PRODUCT.md](docs/PRODUCT.md): positioning against Equal AI, UX principles, plans
- [docs/RESEARCH.md](docs/RESEARCH.md): the research behind each technical decision, with sources
