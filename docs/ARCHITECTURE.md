# Architecture

## How a call reaches the AI (Android)

```
Caller dials the user
   │
   ▼
User's phone ── Pickup's CallScreeningService decides in < 5 s ──┐
   │ rings (contact, rule, paused, ring-first)                   │ declines (unknown caller)
   ▼                                                              ▼
User answers normally                          Carrier "forward when busy" (**67*N#)
                                                                  │
                                                                  ▼
                                           User's assistant number (ExoPhone / Plivo / Twilio)
                                                                  │ webhook + bidirectional audio stream
                                                                  ▼
                                                  Pickup backend: route → voice agent
                                                                  │
          ┌───────────────────────────────────────────────────────┼───────────────────────────────┐
          ▼                                                       ▼                               ▼
 Pipecat pipeline (per call)                         Live events (Redis pub/sub)        Post-call job
 Silero VAD + Smart Turn v3                          → WebSocket when app is open      Claude structured output:
 Sarvam Saaras v3 STT (Hinglish)                     → FCM data push otherwise         summary, category, actions
 Claude (claude-haiku-5-5, effort low)               → Live Update notification        → push + reputation
 Sarvam Bulbul v3 TTS                                  with Reply / Join / End
```

Before declining, the phone posts a **screening hint** with the real caller number. Some carriers
show the forwarding number on forwarded calls; the hint lets the backend fix the caller ID.

### Take over ("Join call")

The provider moves the caller to the user's own number (Twilio call update, Plivo transfer, or for
Exotel the flow's Passthru → Connect applets). The call arrives from the assistant number, which the
screening policy always lets ring. If the user doesn't answer, their forwarding bounces it back to
the assistant number; the backend detects our own number calling itself and plays a short goodbye
instead of answering itself in a loop.

### Forwarding verification

The backend calls the user's phone from their assistant number while the app is in a 2-minute
verification window. The app declines it; if forwarding works, the call lands back on the assistant
number and the line is marked verified. A real forwarded call also verifies the line.

## Components

| Path | What |
|------|------|
| `backend/app/main.py` | FastAPI app, background scheduler and retention sweep |
| `backend/app/routers/` | Mobile API (`account`, `setup`, `calls`, `assistant_chat`), telephony webhooks, admin |
| `backend/app/services/calls.py` | Routing a forwarded call, transcripts, live snapshots, summaries, reputation |
| `backend/app/voice/` | The live call: Pipecat pipeline, take over, owner notes, recording |
| `backend/app/telephony/` | Exotel, Plivo, Twilio adapters behind one interface |
| `backend/app/ai/` | Prompts, structured outputs (live intent, insights), the in-app assistant with tools |
| `backend/evals/` | Simulated-caller conversation evals with an LLM grader |
| `android/app/.../telephony/` | Screening service and the unit-tested screening policy |
| `android/app/.../notify/`, `push/` | Live Update notification, inline reply, FCM handling |
| `android/app/.../ui/` | Compose screens: onboarding, home, live call, call detail, chat, settings |

## API (all under `/v1`, bearer JWT)

| Area | Endpoints |
|------|-----------|
| Sign-in | `POST /auth/firebase`, `POST /auth/dev`, `POST /auth/refresh`, `POST /auth/logout`, `GET /config` |
| Account | `GET/PATCH/DELETE /me`, `POST /devices`, `GET /me/entitlement`, `GET /me/stats`, `POST /stream/ticket` |
| Number and forwarding | `POST /lines`, `GET /lines/current`, `PATCH /lines/{id}`, `POST /lines/{id}/verify`, `DELETE /lines/{id}` |
| Assistant | `GET/PATCH /assistant`, `GET /assistant/options`, `GET/PUT /rules`, `POST /contacts/sync` |
| Screening | `POST /screening/hints`, `GET /screening/policy` |
| Calls | `GET /calls`, `GET /calls/live`, `GET /calls/{id}`, `GET /calls/{id}/recording`, `POST /calls/{id}/say`, `/takeover`, `/end`, `/feedback`, `/actions/{id}`, `/read`, `DELETE /calls/{id}` |
| Assistant chat | `GET/POST /assistant/chat`, `GET/POST /outbound`, `DELETE /outbound/{id}` |
| Billing | `POST /billing/google-play` |
| Live events | `WS /stream?ticket=…` |

FastAPI serves the full OpenAPI spec at `/docs` when the server runs.

### Live event types (WebSocket and push)

`call.started`, `transcript`, `intent`, `call.live` (notification snapshot), `call.state`,
`takeover.ringing`, `call.ended`, `summary`, `line.verified`, `outbound.updated`.

## Data

Postgres in production, SQLite in tests; Alembic migrations in `backend/migrations`.
Tables: users, devices, refresh_tokens, number_pool, lines, assistant_settings, rules, contacts,
screening_hints, calls, transcript_segments, call_actions, outbound_tasks, chat_messages,
number_reputation (salted hashes only, shared across users), purchases.

## Scaling notes

- Each live call holds one WebSocket and one Pipecat pipeline in a single process. Scale out with more
  containers; set `REDIS_URL` so live events and owner commands reach the right instance.
- Host voice workers in the same region as the telephony media servers (Mumbai for Exotel).
- The outbound scheduler runs in every instance. Each due task is claimed with an atomic update, so it
  is dialed exactly once however many instances run.
