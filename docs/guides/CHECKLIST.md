# Your checklist

Server: **https://pickup-ai-i6v0t.fly.dev** (Fly.io, Singapore). Firebase project: `pickup-1e035`.

Every setting you add goes in the same place, always as a **secret**:
**github.com/jokarsv1/pickup-ai → Settings → Secrets and variables → Actions → New repository secret.**
After adding or changing one, tell Claude "redeploy", or run **Actions → Deploy backend (Fly.io) → Run workflow**.

## Done

- Code on GitHub; app and server build automatically on every change
- Server online with HTTPS; Anthropic and Sarvam keys checked and working
- Beta sign-in for your two numbers; push notifications (Firebase) set up, both fingerprints added
- Privacy policy and terms pages live

---

## Do first (5 minutes)

1. **Make the repository private.** github.com/jokarsv1/pickup-ai › **Settings** › **General** › scroll to
   **Danger Zone** › **Change repository visibility** › **Make private** › confirm.
   (It's public now: anyone can read the code and the Actions logs.) iPhone builds then use paid
   macOS minutes: the free plan's 2,000 minutes cover about 20 iPhone builds a month.
2. **Change the beta code.** GitHub secret `BETA_LOGIN_CODE` › **Update** › 6 random digits (not
   123456), then tell Claude "redeploy". Anyone who knows your number could guess `123456`.

## Bucket 1: Install the app and sign in (10 minutes)

1. On your Android phone, open **Chrome** and sign in at **github.com**.
2. Open **github.com/jokarsv1/pickup-ai/actions/runs/44108775220**.
3. Scroll to **Artifacts** at the bottom and tap **pickup-debug-apk**. A zip file downloads.
   (Use this build, not an older one: it lets you skip the phone-number step for now.)
4. Open the **Files** app → **Downloads** → tap **pickup-debug-apk.zip** → **Extract**.
5. Tap **app-debug.apk**.
6. If Android says it isn't allowed to install apps from this source: tap **Settings**, switch on
   **Allow from this source**, then press **Back**.
7. Tap **Install**. If Play Protect warns you: tap **More details → Install anyway**.
8. Open **Pickup** → **Get started** → type your number → **Continue** → enter code **123456**.
9. Type your name, choose languages and a voice → **Continue**.
10. **A few permissions**: tap each item and accept what Android asks (for call screening, choose
    **Pickup** and tap **Set as default**) → **Continue**.
11. You'll see "We're setting up more assistant numbers". That's expected until Bucket 2 is done.
    Tap **Skip for now** → **Go to Pickup**.
12. Try **Ask Pickup** (bottom bar): ask it something, or tell it how to treat delivery calls.

Your second number works the same way. If anything looks wrong, send Claude a screenshot.

## Bucket 2: Real phone calls with Exotel (a few days, mostly waiting)

Calls only reach your AI assistant once you have Indian virtual numbers from Exotel.

**2.1 Get your documents ready.** Exotel's business verification (updated 19 Nov 2026) needs:

If you're on your own (no company), choose **Sole Proprietorship or Individual**:
- Your own **PAN card** number.
- **One** business certificate (PDF/JPG/PNG, under 10 MB): **Udyam (MSME) certificate**,
  Shop & Establishment certificate, or Trade licence. Udyam is the quickest: free, online,
  Aadhaar + PAN, about 15 minutes, only at **udyamregistration.gov.in** (other sites charge for
  the same thing).
- **GST number**, if you have one. If not: choose **GST unregistered** and tick the declaration.
- Your **Aadhaar-linked mobile number** and a phone with a camera (DigiLocker OTP and a selfie).

If you have a **Private Limited / LLP**: company PAN, Certificate of Incorporation, GST number (or
GST exemption proof), names of two directors, and a director as signatory (their Aadhaar-linked
mobile for DigiLocker).

**2.2 Sign up**
1. Go to **exotel.com** → **Sign up** (or "Start free trial"). Use a business email if you have one.
2. If asked for a region, pick **Mumbai** (Exotel recommends it for Indian customers).

**2.3 KYC (about 5 minutes, then a few days of review)**
1. In Exotel: **My Account → Company Info → Start Business Verification**.
2. Enter your PAN → **Verify PAN** → check the name → **Yes, Continue**.
3. Upload the Udyam (or other) certificate → check the name and address it reads →
   **Verify & Continue**.
4. Pick your GSTIN, or **GST unregistered** → tick the declaration → **Continue**.
5. **Send KYC** to your own mobile/email → open the link on your phone → DigiLocker (OTP to your
   Aadhaar mobile) → **Allow** → selfie (allow camera and location) → sign the form →
   "KYC process completed". The link works for 14 days.
6. Stuck anywhere: **Help me verify** (Exotel replies within 24 hours). Details typed in by hand
   take 3 days to review.

**2.4 Ask Exotel to switch on voice streaming** (you can do this while KYC is pending)
1. Find your **Account SID**: in Exotel, open **API Settings** (it lists Account SID, API key and API token).
2. Email **hello@exotel.com**
   - Subject: `Enable Stream/Voicebot Applet for <your Account SID>`
   - Body: `We are building an AI call assistant. Calls are forwarded to our ExoPhones and handled by our bot over WebSocket using the Voicebot applet. Please enable it and share pricing for 2-5 ExoPhones.`

**2.5 Buy 2 ExoPhones** (virtual numbers): one for you, one for your tester. Exotel sales will help.

**2.6 Give the server your Exotel keys**: add these 4 secrets (values from **API Settings**):

| Name | Value |
|---|---|
| `EXOTEL_ACCOUNT_SID` | Account SID |
| `EXOTEL_API_KEY` | API key |
| `EXOTEL_API_TOKEN` | API token |
| `EXOTEL_SUBDOMAIN` | `api.in.exotel.com` (Mumbai account) or `api.exotel.com` (Singapore account) |

Then tell Claude "redeploy".

**2.7 Get your three links**: Actions → **Phone numbers and telephony links** → **Run workflow** →
open the finished run → **Summary**. (Or ask Claude to run it and send you the links.)

**2.8 Build the call flow in Exotel** (App Bazaar → create a new flow):
1. **Voicebot** applet → paste the **Voicebot** link
2. then **Passthru** applet → paste the **Passthru** link
   - if it answers **200** → **Connect** applet, choose dynamic URL → paste the **Connect** link
   - otherwise → **Hangup**
3. Save, and attach this flow to both ExoPhones.

If the flow editor is confusing, send the three links to Exotel support and ask them to set it up on a call.

**2.9 Add the numbers to Pickup**: Actions → **Phone numbers and telephony links** → **Run workflow** →
type both ExoPhones in the box (e.g. `+918047491899, +918047491900`) → **Run workflow**.
(Or send Claude the numbers.)

**2.10 Finish setup in the app**: Home → **Continue setup**. It gives you codes to dial for call
forwarding, then places a test call.

**2.11 Let the assistant make calls for you** (optional: "call the clinic and book a check-up"):
1. In Exotel, App Bazaar → create a **second** flow with only a **Voicebot** applet → paste the
   same **Voicebot** link → Save. Note the flow's number (App ID) shown in its address.
2. GitHub → Settings → Secrets → Actions → **New repository secret**: name
   `EXOTEL_OUTBOUND_FLOW_ID`, value = that number. Then Actions → **Deploy backend** → Run workflow.
3. Ask Exotel support: "We place transactional calls that our users request (appointment booking,
   follow-ups). Please enable DND calling, or tell us what you need." Without this, numbers on
   the Do-Not-Disturb list (many personal mobiles) can't be reached; most businesses can.

## Bucket 3: Before you open it to the public

**3.1 SMS sign-in for everyone** (Firebase)
1. **console.firebase.google.com** → project **Pickup** → **Upgrade** (bottom left) → **Blaze** plan →
   add a billing account. The first 10 SMS a day are free; later ones are charged per SMS.
2. **Build → Authentication → Get started → Sign-in method → Phone → Enable → Save.**
3. Add the secret `FIREBASE_PROJECT_ID` = `pickup-1e035`, then "redeploy".

**3.2 Your details on the privacy policy and terms**: add these secrets, then "redeploy":
`SUPPORT_EMAIL` (email users can write to), `LEGAL_ENTITY_NAME` (your name or company),
`LEGAL_ADDRESS`, `LEGAL_JURISDICTION_CITY` (e.g. `Mumbai`), `GRIEVANCE_OFFICER` (name, usually you).
Before launch, have a lawyer read https://pickup-ai-i6v0t.fly.dev/legal/privacy and /legal/terms.

**3.3 Google Play** (only for the public launch and paid plans)
1. **play.google.com/console** → sign up (one-time $25 fee, ID verification).
2. Google currently asks new personal accounts to run a closed test with at least 12 testers for
   14 days before going public. Your beta testers can be those testers.
3. Tell Claude when the account is approved; Claude sets up the release build and lists the store
   forms to fill in.

## Bucket 3b: iPhone (TestFlight)

iPhone apps install from a TestFlight link instead of a file. It needs an Apple Developer account
(US$99 a year). Click-by-click steps: [IPHONE.md](IPHONE.md).

To try it first for free: https://pickup-ai-i6v0t.fly.dev/install/iphone (Sideloadly and your own
Apple ID on a Mac or Windows computer; no notifications, re-install every 7 days).

## Bucket 4: Housekeeping (15 minutes, any time soon)

The Fly token and Firebase key were shared in chat. Make fresh ones:

**Fly token**
1. **fly.io** dashboard → **Tokens** → **Create token** → copy it.
2. GitHub secrets → `FLY_API_TOKEN` → **pencil (Update)** → paste → **Update secret**.
3. Back in Fly → **Tokens** → old token ("equal Fly") → **Revoke**.

**Firebase key**
1. Firebase → **gear → Project settings → Service accounts → Generate new private key**.
2. GitHub secrets → `FCM_SERVICE_ACCOUNT_JSON` → **Update** → paste the whole new file → **Update secret**.
3. **console.cloud.google.com** → project **Pickup** → **IAM & Admin → Service accounts** →
   `firebase-adminsdk-…` → **Keys** → delete the key starting `00e3f472`.
4. Tell Claude "redeploy".

## Optional

- **AI test run**: Claude can run 8 simulated callers (scammer, delivery, recruiter…) against your
  assistant. It uses part of your Anthropic credit, so it only runs when you ask.


## Reading problem reports from users

Users can send "Report a problem" from Settings in the app. Their note arrives with their setup
details (forwarding status, carrier, SIMs, plan, app version).

1. Make the repository private first (reports contain phone numbers; the workflow refuses to run
   on a public repository).
2. GitHub › your repository › **Actions** › **Support inbox** › **Run workflow** › Run.
3. Open the run when it finishes, then **Summary**: each report shows the note and the details.
4. Reply by calling or WhatsApp-ing the number shown.
