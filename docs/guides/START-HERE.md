# Start here: from code to a working app on your phone

> **Already set up?** Your current to-do list is in [CHECKLIST.md](CHECKLIST.md).

Everything below happens in your web browser: the GitHub website, Fly.io, Firebase, Anthropic and
Sarvam. You don't need to install anything on your laptop or type terminal commands.

Do the steps in order. Each one ends with something you can check.

| Step | Guide | Time | Cost | You'll have |
|------|-------|------|------|-------------|
| 1 | [API keys and beta login](API-KEYS.md) | 15 min | $5 Anthropic credit; Sarvam gives ₹100 free | The AI brain and voice |
| 2 | [Server](HOSTING.md) | 20 min | About $9/month | Your backend online with HTTPS |
| 3 | [Install the test app](INSTALL-APK.md) | 5 min | Free | Pickup on your Android phone, signed in |
| 4 | [Firebase](FIREBASE.md) | 20 min | Free (SMS sign-in later is pay-per-SMS) | Push notifications, and sign-in when you launch |
| 5 | Telephony (Exotel) | A few days (KYC) | Exotel plan + numbers | Real calls reaching your assistant. See [SETUP.md §5](../SETUP.md#5-telephony-exotel-india) |

## Where you'll paste things

All keys and settings go into your GitHub repo's settings, never into chat and never into the code:

**github.com/jokarsv1/pickup-ai → Settings → Secrets and variables → Actions**

- **Secrets** tab: everything below. Nobody can read them back after saving, not even you.
- **Variables** tab: only optional settings (your legal details, overrides).

When you change any of them, go to the **Actions** tab → **Deploy backend (Fly.io)** → **Run workflow**
so the server picks them up.

## The full list

| Name | Type | Example | From |
|------|------|---------|------|
| `FLY_API_TOKEN` | Secret | `FlyV1 fm2_...` | Fly.io dashboard → Tokens |
| `ANTHROPIC_API_KEY` | Secret | `sk-ant-...` | platform.claude.com |
| `SARVAM_API_KEY` | Secret | `sk_...` | dashboard.sarvam.ai |
| `BETA_LOGIN_NUMBERS` | Secret | `+919876543210, +919812345678` | The mobile numbers allowed to sign in |
| `BETA_LOGIN_CODE` | Secret | `482913` | Make up 6+ digits |
| `FCM_SERVICE_ACCOUNT_JSON` | Secret | `{"type": "service_account", ...}` | Firebase → Service accounts (whole file) |
| `FIREBASE_PROJECT_ID` | Variable | `pickup-12345` | Only when you switch on SMS sign-in |
| `SUPPORT_EMAIL`, `LEGAL_ENTITY_NAME`, `LEGAL_ADDRESS`, `GRIEVANCE_OFFICER` | Variables | `you@gmail.com` | Shown on your privacy policy and terms |

The server is **https://pickup-ai-i6v0t.fly.dev** (name set in `backend/fly.toml`). Your privacy policy
and terms are at `/legal/privacy` and `/legal/terms` there: the URLs Firebase and Google Play ask for.
