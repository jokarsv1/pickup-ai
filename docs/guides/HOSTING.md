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

## Step 3: Give GitHub the token and pick a name

On **github.com/jokarsv1/pickup-ai → Settings → Secrets and variables → Actions**:

1. **Secrets** tab → **New repository secret**
   - Name: `FLY_API_TOKEN`
   - Value: the token from step 2
2. **Variables** tab → **New repository variable**
   - Name: `FLY_APP_NAME`
   - Value: a name that's yours, lowercase letters, numbers and dashes, e.g. `pickup-yourname`.
     It must be unique across all of Fly.
3. **Variables** tab → **New repository variable**
   - Name: `PICKUP_API_BASE_URL`
   - Value: `https://` + your app name + `.fly.dev`, e.g. `https://pickup-yourname.fly.dev`

## Step 4: Deploy

1. Click the **Actions** tab → **Deploy backend (Fly.io)** on the left → **Run workflow** → **Run workflow**.
2. Wait 5–10 minutes the first time. The workflow creates the app in Mumbai, creates storage,
   generates the server's passwords, and deploys.
3. When it's green, open `https://YOUR-APP.fly.dev/healthz` in your browser. You should see `{"ok":true}`.

From now on, every code change to `backend/` redeploys automatically. Settings changes need a manual
**Run workflow**.

## Step 5: Update the app

Actions → **Android** → **Run workflow**. The new APK (see [INSTALL-APK.md](INSTALL-APK.md)) talks to
your server.

## Your public pages

- Privacy policy: `https://YOUR-APP.fly.dev/legal/privacy`
- Terms: `https://YOUR-APP.fly.dev/legal/terms`

Fill in your details with the variables `SUPPORT_EMAIL`, `LEGAL_ENTITY_NAME` (your name or company),
`LEGAL_ADDRESS` and `GRIEVANCE_OFFICER` (who handles complaints, often you), then **Run workflow** again.

## If something goes wrong

- **The deploy fails at "Create the app":** the name is taken. Change `FLY_APP_NAME` and run again.
- **The deploy fails at "Deploy" with a billing message:** add a card in Fly → Billing.
- **To see the server's logs:** Fly dashboard → your app → **Monitoring** → **Logs**.

Later, when you have many users, move the database to Postgres (Fly Managed Postgres or Supabase)
by setting `DATABASE_URL`. The code already supports it.
