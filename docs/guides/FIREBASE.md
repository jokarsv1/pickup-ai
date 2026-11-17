# Firebase: push notifications now, SMS sign-in at launch

Firebase does two jobs for Pickup:

1. **Push notifications** (free). They let the app show a live call, with Reply and Join buttons,
   even when it's closed.
2. **SMS sign-in** (pay per SMS). It sends the 6-digit code when you open Pickup to the public.
   Until then, the beta login from [API-KEYS.md](API-KEYS.md) is enough.

## Part 1: Create the project (free)

1. Go to **console.firebase.google.com** and sign in with your Google account.
2. Click **Create a project** (or **Add project**).
3. Name it `Pickup` and click **Continue**. Turn **Google Analytics off** (not needed) and click
   **Create project**, then **Continue**.

## Part 2: Add the Android app

1. On the project's home page, click the **Android** icon ("Add app").
2. Fill in:
   - **Android package name:** `ai.pickup.app` (exactly this)
   - **App nickname:** `Pickup`
   - **Debug signing certificate SHA-1:**
     `9F:13:B7:16:1D:2A:A2:A5:B3:CC:95:C1:2F:B8:C1:74:B3:63:D0:F1`
3. Click **Register app**.
4. Click **Download google-services.json**. Keep the file.
5. Click **Next** through the remaining screens and **Continue to console**. The code is already set up.
6. Click the **gear icon → Project settings**. Under **Your apps → Pickup**, click
   **Add fingerprint** and paste the SHA-256:
   `D6:08:AA:42:E0:7E:CD:46:F4:0C:EB:94:B7:58:96:09:83:C3:A0:CD:2B:41:4E:64:D3:DF:DA:D9:5B:1C:80:BE`
   then **Save**.

These two fingerprints belong to the fixed test key in the repo, so every APK GitHub builds matches them.

## Part 3: Put google-services.json in the code

1. Open **github.com/jokarsv1/pickup-ai**, click into the folders **android** then **app**.
2. Click **Add file → Upload files**, drag in `google-services.json`, and click **Commit changes**.

GitHub rebuilds the APK with Firebase switched on. This file is safe to keep in a private repo.

## Part 4: Let the server send notifications

1. In Firebase: **gear icon → Project settings → Service accounts** tab.
2. Click **Generate new private key → Generate key**. A `.json` file downloads.
   **This one is a real secret**: never share it or commit it.
3. Open the file in Notepad (or TextEdit), select everything, and copy it.
4. In GitHub: **Settings → Secrets and variables → Actions → Secrets → New repository secret**
   - Name: `FCM_SERVICE_ACCOUNT_JSON`
   - Value: paste the whole file contents
5. **Actions → Deploy backend (Fly.io) → Run workflow.**

Install the new APK, sign in, and allow notifications. Push is now on.

## Part 5 (at launch): SMS sign-in

Do this when you want anyone, not just beta numbers, to sign up.

1. Firebase requires the **Blaze** (pay-as-you-go) plan for SMS. Click **Upgrade** at the bottom of
   the left menu and add a billing account. The first 10 SMS a day are free; after that each SMS
   costs a few cents (see the Firebase pricing page for India).
2. **Build → Authentication → Get started → Sign-in method → Phone → Enable → Save.**
   Optionally add test phone numbers with fixed codes there (they never send real SMS).
3. In GitHub: **Variables** tab → `FIREBASE_PROJECT_ID` = the **Project ID** shown in Project
   settings → General (e.g. `pickup-1a2b3`).
4. **Actions → Deploy backend (Fly.io) → Run workflow.**

The app switches to real SMS codes automatically. Beta numbers keep working with the beta code.
