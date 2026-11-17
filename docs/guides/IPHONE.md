# The iPhone app: install it from a link (TestFlight)

Apple doesn't allow installing apps from a file the way Android does. The equivalent of the
Android APK is **TestFlight**: Apple's beta-testing app. You (and up to 10,000 testers) install
Pickup from a link, without an App Store listing. It needs a paid Apple Developer account.

| | Cost | Time |
|---|---|---|
| Apple Developer Program | US$99 a year (charged in rupees) | Sign-up 10 min; Apple's approval up to 2 days |
| Everything else | Free | About 30 minutes, once |

## Try it today, free (no Apple Developer account)

Every push to `main` that changes the iPhone app also publishes an unsigned **preview** build.
You install it with your own Apple ID using **Sideloadly** on a Mac or Windows computer.

1. Open `https://<your-app>.fly.dev/install/iphone` (for you: https://pickup-ai-i6v0t.fly.dev/install/iphone).
2. Follow the steps on that page: download the file, drag it into Sideloadly, enter your Apple ID,
   then turn on Developer Mode and trust your Apple ID on the iPhone.

The limits are Apple's, for free accounts:

- **No notifications.** Pickup updates while it's open, but can't alert you about a call or show it
  on the Lock Screen. That needs the paid account (Steps 1-6 below).
- **It stops opening after 7 days.** Install it again from the computer (Sideloadly can do this by
  itself when the iPhone is on the same Wi-Fi). Nothing is lost: your calls live on the server.
- At most 3 apps installed this way per iPhone.

Use the preview to try the app; use TestFlight (below) for daily use and for testers.

## How Pickup works on iPhone (different from Android)

iPhone doesn't let apps decline calls for you, so Pickup can't screen calls automatically like on
Android. Instead:

- **You decline (or don't pick up)** a call, and your carrier forwards it to your assistant.
- **Optional automatic mode:** turn on *Silence Unknown Callers* (Settings › Apps › Phone). Calls
  from numbers that aren't in your contacts then go straight to your assistant, while contacts
  still ring. (Test it with your carrier: it should behave like a declined call.)
- iPhone can't dial forwarding codes from an app, so the app shows each code with a **Copy**
  button: paste it on the Phone keypad and press call.

Everything else is the same: live transcript, replies, Join, summaries and Ask Pickup.

## Step 1: Join the Apple Developer Program

1. On your iPhone, install the **Apple Developer** app from the App Store and open it.
2. Tap **Account**, sign in with your Apple ID (it needs two-factor authentication on), then
   **Enroll now**. Enroll as an **Individual** (a company needs a D-U-N-S number).
3. Scan your ID when asked, pay, and wait for the "Welcome to the Apple Developer Program" email.

## Step 2: Register the app's ID

1. On a computer, go to **developer.apple.com/account** › **Certificates, IDs & Profiles** ›
   **Identifiers** › **+**.
2. Choose **App IDs** › **App** › Continue.
3. Description: `Pickup`. Bundle ID: **Explicit**, `ai.pickup.app`.
   If Apple says it's taken, use something like `in.yourname.pickup` and remember it.
4. Under Capabilities, tick **Push Notifications**. Click **Continue** › **Register**.

## Step 3: Create the app in App Store Connect

1. Go to **appstoreconnect.apple.com** › **Apps** › **+** › **New App**.
2. Platform **iOS**; Name `Pickup AI Assistant` (names must be unique on the App Store; any
   name works for TestFlight); Language **English (India)**; Bundle ID: the one from step 2;
   SKU `pickup-ios`; Full Access. Click **Create**.

## Step 4: Let GitHub upload builds (API key)

1. In App Store Connect: **Users and Access** › **Integrations** › **App Store Connect API** ›
   **Team Keys** › **+**.
2. Name `GitHub`, Access **Admin** (needed to create the signing certificate). **Generate**.
3. **Download** the key file (`AuthKey_XXXX.p8`). You can only download it once.
4. Note the **Key ID** (in the list) and the **Issuer ID** (above the list).
5. Find your **Team ID**: developer.apple.com/account › **Membership details**.
6. Add these **GitHub secrets** (repo › Settings › Secrets and variables › Actions › New repository secret):

| Name | Value |
|---|---|
| `APPLE_TEAM_ID` | Team ID, e.g. `A1B2C3D4E5` |
| `ASC_KEY_ID` | Key ID |
| `ASC_ISSUER_ID` | Issuer ID |
| `ASC_PRIVATE_KEY` | The whole `.p8` file: open it in a text editor and copy everything |
| `IOS_BUNDLE_ID` | Only if you didn't use `ai.pickup.app` |

## Step 5: Push notifications for iPhone (APNs key)

1. developer.apple.com/account › **Certificates, IDs & Profiles** › **Keys** › **+**.
2. Name `Pickup push`, tick **Apple Push Notifications service (APNs)**, Continue › Register.
3. **Download** the `.p8` file and note its **Key ID**.
4. Add GitHub secrets `APNS_KEY_P8` (the whole file) and `APNS_KEY_ID`, then run
   **Actions › Deploy backend (Fly.io) › Run workflow** (or ask Claude to redeploy).

## Step 6: Build and install

1. **Actions › iOS TestFlight › Run workflow** (or ask Claude). About 15 minutes; Apple then
   processes the build for 10–30 minutes.
2. In App Store Connect › your app › **TestFlight** › **Internal Testing** › **+**, create a
   group, add yourself, and add the build.
3. On your iPhone, install **TestFlight** from the App Store and open the invite email
   (or the link in TestFlight). Tap **Install**.
4. To invite others: **External Testing** › create a group › add the build › **Submit for
   review** (the first build only, usually within a day) › **Enable public link**. Share the link.

TestFlight builds stay installable for 90 days; each new build from the workflow replaces the old one.
