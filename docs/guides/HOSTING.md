# Put the server online (Fly.io, about $7 a month)

The backend needs a public **https://** address, because phone companies and the app must be able
to reach it. **Fly.io** gives you one automatically (`https://your-app.fly.dev`, no domain to buy),
has a **Mumbai** data centre close to your callers, and GitHub can deploy to it for you.

**Cost:** one always-on machine with 1 GB of memory is about **$7/month**, plus storage at $0.15/GB.
If a month's bill is under $5, Fly waives it. New accounts get a small free trial without a card;
add a card to keep the server running.

## Step 1: Create a Fly.io account

1. Go to **fly.io** and click **Sign up**. "Sign up with GitHub" is easiest.
2. In the dashboard, open **Billing** and add a payment card.

## Step 2: Create a deploy token

1. In the Fly dashboard, open **Tokens** in the left sidebar (under your organization, usually "Personal").
2. Click **Create token**, name it `github-deploy`, and set a long expiry (or none).
3. Copy the token. It starts with `FlyV1`.

## Step 3: Give GitHub the token

On **github.com/jokarsv1/pickup-ai → Settings → Secrets and variables → Actions → Secrets** tab →
**New repository secret**:

- Name: `FLY_API_TOKEN`
- Value: the whole token from step 2, starting with `FlyV1`

The app's name is already chosen in `backend/fly.toml` (`pickup-ai-i6v0t`), so your server will be
**https://pickup-ai-i6v0t.fly.dev** and the APK already points there. You don't need to set
`FLY_APP_NAME` or `PICKUP_API_BASE_URL`; they only override those defaults.

## Step 4: Deploy

1. Click the **Actions** tab → **Deploy backend (Fly.io)** on the left → **Run workflow** → **Run workflow**.
2. Wait 5–10 minutes the first time. The workflow creates the app in Mumbai, creates storage,
   generates the server's passwords, and deploys.
3. When it's green, open **https://pickup-ai-i6v0t.fly.dev/healthz** in your browser. Seeing
   `{"ok":true}` means the server is running. The last step of the run also says whether your
   Anthropic and Sarvam keys work.

From now on, every code change to `backend/` redeploys automatically. Settings changes need a manual
**Run workflow**.

## Step 5: Install the app

Every APK GitHub builds already talks to this server. See [INSTALL-APK.md](INSTALL-APK.md).

## Your public pages

- Privacy policy: `https://pickup-ai-i6v0t.fly.dev/legal/privacy`
- Terms: `https://pickup-ai-i6v0t.fly.dev/legal/terms`

Fill in your details with the variables `SUPPORT_EMAIL`, `LEGAL_ENTITY_NAME` (your name or company),
`LEGAL_ADDRESS` and `GRIEVANCE_OFFICER` (who handles complaints, often you), then **Run workflow** again.

## If something goes wrong

- **The deploy fails at "Check the Fly token":** create a new token in Fly and replace the `FLY_API_TOKEN` secret.
- **The deploy fails at "Create the app":** add a card in Fly → Billing. If the error says the name is
  taken, change `app` in `backend/fly.toml` and `pickup.apiBaseUrl` in `android/gradle.properties`.
- **The deploy fails at "Deploy" with a billing message:** add a card in Fly → Billing.
- **To see the server's logs:** Fly dashboard → your app → **Monitoring** → **Logs**.

Later, when you have many users, move the database to Postgres (Fly Managed Postgres or Supabase)
by setting `DATABASE_URL`. The code already supports it.
