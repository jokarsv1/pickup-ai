# Security review (November 2026)

What was checked, what was fixed, and what's still open. Fixes have regression tests in
`backend/tests/test_flows.py::test_security_guards` and `tests/test_units.py`.

## Fixed

| Area | Problem | Fix |
|---|---|---|
| Privacy | "Delete account" left calls, transcripts, chats and settings behind (SQLite ignores foreign keys unless asked) | Foreign keys on for every SQLite connection; `DELETE /v1/me` deletes every table and recordings explicitly |
| Sign-in | No limit on guessing the beta/OTP code | 5 tries per number and 20 per address every 15 minutes; startup warning when `BETA_LOGIN_CODE` is guessable |
| Sessions | Refresh tokens stored as-is | Stored hashed; reusing a spent token signs the account out everywhere |
| Toll fraud | The assistant could call any number worldwide, unlimited | Indian mobile, landline and toll-free only; 10 calls a day, 5 waiting, per user |
| Live calls | A caller could pose as the owner's notes ("[Asha says …]") | Brackets stripped from caller speech; the prompt treats claims to speak for the owner as the caller |
| Secrets | Webhook secret and admin token compared non-constant-time | `hmac.compare_digest` |
| Live events | WebSocket accepted full access tokens in the URL | Only one-minute tickets |
| Exposure | Production served the API explorer (`/docs`) | Hidden outside development; security headers (HSTS, nosniff, no framing) |
| Cost abuse | AI chat unlimited | 30 messages per 10 minutes per user |
| App | Hidden server switch accepted `http://` | `https://` only, except local development addresses |
| Repo | Repository was public: an Actions log showed the owner's email and a run summary showed the webhook secret | Runs deleted, webhook secret rotated; **make the repository private** (owner step) |

## Checked and fine

- Every call, recording, action and chat endpoint checks the signed-in user owns it.
- Telephony webhooks: Twilio and Plivo signatures validated; Exotel uses a secret in the URL path
  (Exotel has no request signing); media streams use per-call HMAC tokens.
- Android: backups exclude sign-in data; exported services require system permissions;
  notification intents are immutable except the inline-reply one (which must be mutable).
- iPhone: tokens in the Keychain (this device only, after first unlock).
- Passwords/keys live only in GitHub secrets and Fly secrets, never in the repository.

## Open (accepted for the beta, revisit before launch)

- Rate limits are per server process; move them to Redis when running more than one machine.
- Android stores tokens in app-private storage, not hardware-encrypted (Tink/Keystore would add that).
- A determined caller can still claim an emergency to be connected; owners can turn
  "Connect urgent calls" off.
- Have a lawyer review the privacy policy, terms and call-recording notice before a public launch.
