# What's left for you

Everything that can be built without your accounts, money or signature is built and tested.
This is the complete list of what's left, in the order that unblocks the most.

Every key goes into `backend/.env` (copy `backend/.env.example`). Nothing needs a code change.

| # | What | Unblocks | Where it goes |
|---|------|----------|---------------|
| 0 | GitHub repo `pickup-ai` | Pushing the code; Android builds in CI | `git remote` |
| 1 | Anthropic API key | Live call brain, summaries, chat; the eval suite | `ANTHROPIC_API_KEY` |
| 2 | Sarvam AI key | Speech-to-text and voices for Indian languages | `SARVAM_API_KEY` |
| 3 | Firebase project | Real OTP sign-in and push notifications | `google-services.json`, `FIREBASE_PROJECT_ID`, `FCM_SERVICE_ACCOUNT_FILE` |
| 4 | A server with HTTPS | Telephony webhooks need a public URL | `PUBLIC_BASE_URL`, `DATABASE_URL`, `REDIS_URL` |
| 5 | Exotel account and numbers | Calls actually reaching the AI | `EXOTEL_*` + flows |
| 6 | Google Play Console | Publishing and subscriptions | Play Console + `GOOGLE_PLAY_SERVICE_ACCOUNT_FILE` |
| 7 | Legal pages and policies | Play Store approval, user trust | Hosted URLs |

---

## 0. GitHub repository

Cloud sessions can't create repositories, so the code is committed but not yet pushed.

1. Create an empty **private** repo named `pickup-ai` at github.com/new (no README or .gitignore).
2. Ask Claude Code to "push to jokarsv1/pickup-ai", or from a local clone of this work:

```bash
git remote add origin git@github.com:jokarsv1/pickup-ai.git
```

```bash
git push -u origin main
```

GitHub Actions then runs the backend tests and builds the Android app. Download the debug APK from
the run's **Artifacts** section (`pickup-debug-apk`).

## 1. Anthropic API key

1. Create a key at platform.claude.com → API keys.
2. Set `ANTHROPIC_API_KEY`. Models default to `claude-opus-5-5` (`CLAUDE_MODEL`).
3. Try the agent right away, no phone line needed:

```bash
cd backend && python -m scripts.chat_with_agent --owner "Your Name"
```

```bash
cd backend && python -m evals.run_evals -v
```

The eval suite plays eight realistic callers (Hinglish delivery agent, KYC scammer, recruiter,
family emergency…) against the live prompt and grades the results. Run it before every prompt change.

## 2. Sarvam AI (speech for Indian languages)

1. Sign up at dashboard.sarvam.ai and create an API key.
2. Set `SARVAM_API_KEY`. Defaults: `saaras:v3-realtime` (speech-to-text, handles Hinglish) and
   `bulbul:v3` (voices: ritu, priya, neha, kavya, shubh, aditya, rahul, dev).

Outside India, set `STT_PROVIDER=deepgram` and `TTS_PROVIDER=elevenlabs` or `cartesia` with their keys instead.

## 3. Firebase (sign-in and push)

1. Create a project at console.firebase.google.com.
2. **Add an Android app** with package name `ai.pickup.app`. Add the SHA-1 and SHA-256 of your
   debug and release signing keys (`./gradlew signingReport` in `android/` prints them).
3. Download `google-services.json` into `android/app/`. The build picks it up automatically.
4. **Authentication → Sign-in method → Phone**: enable it. Add a test number with a fixed code for development.
5. **Project settings → Service accounts → Generate new private key**: save the JSON on the server
   and set `FCM_SERVICE_ACCOUNT_FILE` to its path.
6. Set `FIREBASE_PROJECT_ID` to the project id.

Until this is done, the app signs in with the development code `123456` and shows live updates
only while it is open.

## 4. Hosting

The backend is one Docker image (`backend/Dockerfile`). It runs migrations on start.

- Pick a region near your telephony provider's media servers (Mumbai for Exotel) to keep replies fast.
- You need Postgres, Redis (for more than one instance) and a public HTTPS URL. Render, Railway,
  Fly.io or AWS `ap-south-1` all work.
- Set `ENV=prod`, `PUBLIC_BASE_URL=https://your-domain`, `DATABASE_URL=postgresql+asyncpg://…`,
  `REDIS_URL`, and long random values for `JWT_SECRET`, `ADMIN_TOKEN`, `TELEPHONY_WEBHOOK_SECRET`.
- Recordings: set `S3_BUCKET` (and `S3_ENDPOINT_URL` for non-AWS storage).

For a first test from your laptop: `docker compose up --build`, then expose port 8000 with
`cloudflared tunnel --url http://localhost:8000` or ngrok, and use that URL as `PUBLIC_BASE_URL`.
In the app, long-press the logo on the welcome screen to point it at that server.

## 5. Telephony: Exotel (India)

Twilio can't place India-to-India calls, so Exotel is the default for India (Plivo and Twilio
adapters are included for other markets).

1. Open an Exotel account and complete business KYC. Indian virtual numbers need it.
2. Rent ExoPhones. **Each user needs one** (that's how the backend knows whose call it is).
   Start with a handful for testing.
3. In **App Bazaar**, build the inbound flow and attach it to every ExoPhone:
   - **Voicebot** applet → URL `https://YOUR_DOMAIN/telephony/exotel/YOUR_WEBHOOK_SECRET/voicebot`
   - then **Passthru** applet → URL `https://YOUR_DOMAIN/telephony/exotel/YOUR_WEBHOOK_SECRET/passthru`
     - on **200** → **Connect** applet with dynamic URL `https://YOUR_DOMAIN/telephony/exotel/YOUR_WEBHOOK_SECRET/connect`
     - otherwise → **Hangup**
4. Build a second flow for outbound calls (just the Voicebot applet with the same URL) and put its
   id in `EXOTEL_OUTBOUND_FLOW_ID`.
5. Set `EXOTEL_ACCOUNT_SID`, `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN` (and `EXOTEL_SUBDOMAIN=api.in.exotel.com`
   if your account is on the Mumbai cluster).
6. Load the numbers into the pool:

```bash
cd backend && python -m scripts.add_numbers --provider exotel +9180XXXXXXXX +9180YYYYYYYY
```

**Using Plivo instead:** set `TELEPHONY_PROVIDER=plivo`, `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`, and point each
number's Answer URL at `https://YOUR_DOMAIN/telephony/plivo/inbound` (POST).
**Twilio (outside India):** same with `https://YOUR_DOMAIN/telephony/twilio/inbound` as the Voice webhook.

## 6. Google Play

1. Create a Play Console developer account and the app `ai.pickup.app`.
2. **Subscriptions:** create `pickup_pro_monthly` and `pickup_pro_yearly` (or change
   `PLAY_PRO_PRODUCT_IDS`). Add a 7-day free trial offer if you want Play to manage trials.
3. **Purchase verification:** in Google Cloud, create a service account, enable the
   *Google Play Android Developer API*, invite the account in Play Console → Users and permissions
   with "View financial data", download its JSON and set `GOOGLE_PLAY_SERVICE_ACCOUNT_FILE`.
4. **Release signing:** create an upload key (Play App Signing) and add its SHA-1/SHA-256 to Firebase.
5. **App content:** the Data safety form must declare contacts (used to let contacts ring through),
   phone state (SIM count) and call audio processed on the server. The call screening role needs no
   special Play declaration, but explain it in the listing.

## 7. Legal and trust

- Privacy policy and terms URLs (required by Play and Firebase).
- Call recording disclosure: the assistant's greeting already says calls may be recorded, and users can
  switch recording off. Check this against current Indian rules with a lawyer.
- DPDP Act 2023: name a grievance officer, honour deletion (the app's **Delete account** already
  deletes everything server-side), and keep the retention setting (default 90 days) honest.
- From July 2026, Indian carriers SMS users whenever forwarding is switched on. The app warns users
  to expect it.

---

## What already works without any of this

- `docker compose up` runs the full backend. The API, the app's sign-in (code `123456`), onboarding,
  settings, history and chat endpoints all work. Without AI keys, calls end politely instead of hanging.
- `pytest` in `backend/` runs 14 tests covering every flow with fake telephony, push and AI.
- The Android app builds on GitHub Actions and runs against that backend. Real calls need items 1-5.
