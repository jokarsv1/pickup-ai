# API keys: exactly what's needed

Two keys run the assistant. Save each one as a **GitHub secret** (Settings → Secrets and variables →
Actions → Secrets → **New repository secret**). Don't paste keys into chat or into the code.

## 1. Anthropic (Claude): the assistant's brain

Used for: the live conversation, the summary after each call, and the "Ask Pickup" chat.

1. Go to **platform.claude.com** and sign up (Google sign-in works).
2. Open **Settings → Billing** and click **Buy credits**. $5 is enough to test for weeks.
3. Open **API keys** → **Create key**, name it `pickup-server`, and copy it. It starts with `sk-ant-`.
   You can only see it once.
4. In GitHub, add a secret named exactly **`ANTHROPIC_API_KEY`** and paste the key.

Rough cost: about ₹4–7 per screened call, for the conversation plus summary. That's an estimate;
your Anthropic dashboard shows the real usage.

**Check it works:** GitHub → Actions → **Agent evals** → **Run workflow**. In about 5 minutes you'll
see eight simulated callers (a Hinglish delivery agent, a KYC scammer, a recruiter…) and how your
assistant handled each one.

## 2. Sarvam AI: the voice (Indian languages)

Used for: understanding what callers say (speech-to-text, including Hinglish) and the assistant's voice.

1. Go to **dashboard.sarvam.ai** and sign up. New accounts get **₹100 of free credit**.
2. Open **API keys** (or **Subscriptions → API keys**) → **Create**, and copy the key.
3. In GitHub, add a secret named exactly **`SARVAM_API_KEY`** and paste the key.

Cost: speech-to-text ₹30 per hour and voice ₹3 per 1,000 characters, so roughly ₹2–3 per minute
of call.

## 3. Your beta login (no SMS cost)

So you can sign in before paying for SMS verification:

1. **Variables** tab → **New repository variable**: `BETA_LOGIN_NUMBERS` = your mobile number with
   country code, e.g. `+919876543210`. Add more numbers separated by commas for testers.
2. **Secrets** tab → **New repository secret**: `BETA_LOGIN_CODE` = 6 or more digits you make up.

Only those numbers can sign in, and only with that code.

## After adding keys

Actions → **Deploy backend (Fly.io)** → **Run workflow**. The last step prints your server's
settings. `"voice_ready": true` means both keys are in place.
