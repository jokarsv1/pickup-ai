# Install the test app (no Play Store needed)

GitHub builds a test version of the app (an APK file) every time the code changes. You can install
it directly on any Android 10 or newer phone. Google Play is only needed later, to publish
to the public and to sell subscriptions.

## Download the APK

1. Open **github.com/jokarsv1/pickup-ai** and click the **Actions** tab.
2. Click **Android** on the left, then the newest run with a green tick.
3. Scroll to **Artifacts** at the bottom and click **pickup-debug-apk**. A zip file downloads.
4. Unzip it. Inside is `app-debug.apk`.

On your phone you can do this in Chrome (sign in to GitHub), or download it on your laptop and send
the APK to yourself (Google Drive, WhatsApp to yourself, or a USB cable).

## Install it

1. On the phone, tap `app-debug.apk`.
2. Android asks whether to allow installs from this source (Chrome, Files or Drive). Tap
   **Settings**, switch on **Allow from this source**, and go back.
3. Tap **Install**. If Play Protect warns about an unknown developer, tap **More details → Install anyway**.
   That warning appears for any app that isn't from the Play Store.

To update later, install the newer APK over the old one. Your sign-in and settings stay.

## Point it at your server

Until your server exists, the app can't do much. After [HOSTING.md](HOSTING.md):

- Add the variable `PICKUP_API_BASE_URL` (for example `https://pickup-yourname.fly.dev`) and re-run
  the **Android** workflow. Every new APK then talks to your server, or
- on the app's welcome screen, **long-press the app logo at the top** and type your server address.

## What works at each stage

| You've done | What works on the phone |
|-------------|-------------------------|
| Server + beta login | Sign in with your beta code, onboarding, settings, instructions |
| + API keys | "Ask Pickup" chat; calling your assistant's number once telephony is set up |
| + Firebase push | Live call notifications with reply and join, even when the app is closed |
| + Exotel numbers | Real calls declined by Pickup reach your assistant, with summaries |
