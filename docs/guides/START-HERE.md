# Start here: from code to a working app on your phone

Everything below happens in your web browser: the GitHub website, Fly.io, Firebase, Anthropic and
Sarvam. You don't need to install anything on your laptop or type terminal commands.

Do the steps in order. Each one ends with something you can check.

| Step | Guide | Time | Cost | You'll have |
|------|-------|------|------|-------------|
| 1 | [Install the test app](INSTALL-APK.md) | 5 min | Free | Pickup on your Android phone |
| 2 | [API keys](API-KEYS.md) | 15 min | $5 Anthropic credit; Sarvam gives ₹100 free | The AI brain and voice |
| 3 | [Server](HOSTING.md) | 20 min | About $7/month | Your backend online with HTTPS |
| 4 | [Firebase](FIREBASE.md) | 20 min | Free (SMS sign-in later is pay-per-SMS) | Push notifications, and sign-in when you launch |
| 5 | Telephony (Exotel) | A few days (KYC) | Exotel plan + numbers | Real calls reaching your assistant. See [SETUP.md §5](../SETUP.md#5-telephony-exotel-india) |

## Where you'll paste things

All keys and settings go into your GitHub repo's settings, never into chat and never into the code:

**github.com/jokarsv1/pickup-ai → Settings → Secrets and variables → Actions**

- **Secrets** tab: anything private (API keys, tokens, the beta login code). Nobody can read them
  back after saving, not even you.
- **Variables** tab: non-secret settings (app name, your phone number for beta login).

When you change any of them, go to the **Actions** tab → **Deploy backend (Fly.io)** → **Run workflow**
so the server picks them up.

## The full list

| Name | Type | Example | From |
|------|------|---------|------|
| `FLY_API_TOKEN` | Secret | `FlyV1 fm2_...` | Fly.io dashboard → Tokens |
| `FLY_APP_NAME` | Variable | `pickup-yourname` | You choose (lowercase, unique) |
| `PICKUP_API_BASE_URL` | Variable | `https://pickup-yourname.fly.dev` | `https://` + app name + `.fly.dev` |
| `ANTHROPIC_API_KEY` | Secret | `sk-ant-api03-...` | platform.claude.com |
| `SARVAM_API_KEY` | Secret | `sk_...` | dashboard.sarvam.ai |
| `BETA_LOGIN_NUMBERS` | Variable | `+919876543210` | Your mobile number(s), comma-separated |
| `BETA_LOGIN_CODE` | Secret | `482913` | Make up 6+ digits you'll remember |
| `FCM_SERVICE_ACCOUNT_JSON` | Secret | `{"type": "service_account", ...}` | Firebase → Service accounts |
| `FIREBASE_PROJECT_ID` | Variable | `pickup-12345` | Only when you switch on SMS sign-in |
| `SUPPORT_EMAIL`, `LEGAL_ENTITY_NAME`, `LEGAL_ADDRESS`, `GRIEVANCE_OFFICER` | Variables | `you@gmail.com` | Shown on your privacy policy and terms |

Your privacy policy and terms are then live at `https://YOUR-APP.fly.dev/legal/privacy` and
`https://YOUR-APP.fly.dev/legal/terms`. Those are the URLs Firebase and Google Play ask for.
