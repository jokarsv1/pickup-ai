# What Equal AI's users say, and what Pickup does about it

Researched 18 November 2026. Sources: about 190 Google Play reviews (India storefront, 1-5
stars, "most relevant" and "newest"), 47 App Store reviews (India), Equal's developer replies,
competitor write-ups (hiRobin, Kuku AIVA) and TRAI's 18 September 2026 regulation.

Equal AI: Play 4.2 stars from 33.1K reviews. Many 5-star reviews are near-identical templates
("The application has a straightforward design concept..."), and one 3-star reviewer says so; we
weighted the specific, detailed reviews.

## The complaints (treated as complaints about Pickup)

Ranked by how often they came up and how angry people were.

| # | Theme | What users said | Pickup's fix |
|---|---|---|---|
| 1 | **The assistant doesn't answer** | "failed to respond even a single call from unknown number, in last ten days"; "works fine for the first few days, then stops"; "Most of the missed calls were not captured" | Carrier forwarding silently drops 30-43% of calls (hiRobin's telemetry) and forgets rules. Pickup now notices: the phone tells the server each call it sends on, and if the call never arrives, you get "A call from +91… didn't reach your assistant" with Call back, plus a one-tap fix when it keeps happening. |
| 2 | **Setup fails** | "Something went wrong during activation"; "Setup Failed even after restarting"; BSNL not working | Already: codes are dialled by you, one at a time, with a live test call and plain errors. Added: a re-check you can run any time, and help if a carrier rejects a code. |
| 3 | **Privacy fear** | "uploads all your contacts to an ai server"; "set up call forwarding 2 times without my permission"; "uninstalled and it still forwards"; "can read our OTP" | Pickup no longer uploads your contacts: your phone sends only the caller's name for the one call it hands over. Forwarding is only ever turned on by you, never unconditional; the app shows the off code (##004#) in Settings and before you delete your account. The assistant never asks for or repeats OTPs. |
| 4 | **Slow and silent** | "first 'Hello' comes much later"; "caller says hello hello"; "15 to 20 seconds to respond" | The greeting is now ready before the call connects (synthesised while the carrier sets up the call), and it plays before any database or notification work. |
| 5 | **Conversation quality** | "repeats questions already answered"; "robotic"; "speaks Malayalam instead of Kannada"; male voice speaking as female; "identified a caller as a 'Doctor' just because the caller claimed to be one"; the app said a friend talked about a project when the AI never answered | Already: replies in the caller's language, gendered self-reference matches the voice, never asks twice. Added: summaries report claims as claims ("says he's a doctor"), and a call with nothing said gets a plain "The caller didn't say anything" instead of an invented summary. |
| 6 | **Hangs up on people** | "it responded the caller that I am busy and dropped the call, while I was writing a msg"; "ending them saying I'm busy" | When you start typing a reply, the assistant tells the caller to hold on and keeps the call open. |
| 7 | **Important calls blocked** | "calls from patients automatically rejected"; "office calls were missed" | Contacts always ring unless you choose otherwise. Added: the same number calling twice within 3 minutes rings through (an urgent caller usually tries again); calls from banks and government on 1600/1601 numbers ring by default. Urgent callers can still be put through to you mid-call. |
| 8 | **Paywalled their own calls** | "you can't even hear how the assistant handled the call unless you pay"; "after collecting our data, they started subscription"; "it says free but subscribed" | Your calls, summaries, transcripts and recordings are free forever. Plans limit only how many calls the assistant answers each month and AI outbound calls. The app says plainly what happens after the trial. |
| 9 | **No support** | "customer helpline number is fake"; "no response for support mail"; "kept on hold for over 25 minutes" | In-app Help: a self-check of your setup, and "Report a problem" that sends the diagnostics with your note, so we can answer without back-and-forth. |
| 10 | **Missing controls** | VIP/family ring through; ring time ("pickup within 3 rings"); dual SIM; more languages | Already in Pickup: contacts and "always ring" numbers, ring time 5-30 s, dual-SIM checks, 9 languages. |

## What people love (double down)

1. **Knowing why someone's calling before deciding**, with a live transcript and one-tap take
   over. Pickup: live banner, live notification with quick replies, iPhone Live Activity.
2. **Deliveries handled while busy** (school, meetings): delivery notes and quick replies.
3. **Summaries, transcripts and recordings to review later** ("no longer pulled out of deep
   work"). Pickup keeps them free.
4. **Natural Indian-language voices** ("without annoying robotic tone"; Tamil, Bengali).
5. **Pause the assistant** when you want to answer yourself: Quick Settings tile and snooze.
6. **Call-back reminders** from next steps.

## Regulation we must follow (TRAI, 18 September 2026)

The TCCCPR (Third Amendment) Regulations, 2026, Regulation 34A: call-management apps must not
blanket block, filter or spam-tag calls from **140xx** (registered promotional), **1600xx**
(banks, insurers, government) or **1601xx** (service calls from other sectors). Users may still
block or filter on their own devices, and any "report spam" feature must send reports to the
operators' DLT platform.

Pickup now:
- never marks these numbers as spam, and never counts them in its spam reputation;
- rings 1600/1601 calls by default (they are verified banks, insurers, government and service
  calls), with a setting to let the assistant take them instead;
- labels them so you know what they are ("Verified bank or government number");
- has no "report spam" button (Block stays: that's your own choice on your phone).

Have a lawyer confirm this reading before launch.

## Sources

- Google Play: https://play.google.com/store/apps/details?id=in.equal.ai.assistant
- App Store: https://apps.apple.com/in/app/id6757906431
- hiRobin, "Why Call Forwarding Fails on Airtel, Jio, and Vi": https://www.hirobin.ai/blog/call-forwarding-failures-india
- TRAI notification, 18 September 2026: https://www.trai.gov.in/sites/default/files/2026-09/Regulation_18092026.pdf
- PIB summary: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2311989
- Kuku AIVA comparison: https://kukuaiva.app/blogs/ai-call-assistants-compared/
