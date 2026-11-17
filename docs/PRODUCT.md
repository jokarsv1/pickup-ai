# Pickup: product

**One line:** an AI assistant that answers the calls you can't or don't want to take, finds out who's
calling and why, and tells you in seconds.

## Why we can beat Equal AI

Equal AI (1M+ monthly users, $30M Series B in June 2026) proved Indians want this. Its App Store
reviews show where it's weak, and each weakness maps to a decision in Pickup:

| What Equal's users complain about | What Pickup does |
|---|---|
| "The AI doesn't always pick up" | Forwarding is verified with a real test call before we say "you're live"; a real forwarded call re-verifies; dual-SIM phones never decline a call that can't be forwarded |
| "First hello comes much later" | The greeting is spoken the instant the stream opens, before any model call; streaming speech-to-text, Claude at low effort and streaming text-to-speech keep turns short |
| "Sounds robotic" | Sarvam Bulbul v3 voices built for Indian speech, eight to choose from |
| "Repeats questions already answered" | The prompt tracks what's known and forbids re-asking; an eval scenario checks it on every change |
| "Instructions are missed 4 out of 5 times" | Instructions, packs, per-category rules and a delivery note go into the system prompt; the eval suite grades instruction-following |
| No control while a call is happening (iPhone) | Android Live Update notification with the transcript, smart replies as one-tap choices, Join and End, without opening the app |

Further differentiators:
- **Caller reputation network:** every summary feeds a privacy-preserving (salted hash) reputation per
  number, so the next user's assistant already knows "usually a loan sales call".
- **Assistant that acts:** "call the clinic tomorrow at 10 and book a checkup" schedules an outbound
  call with that goal; reminders and contacts come back as one-tap actions.
- **Ring first, then assistant:** the most requested setting in Equal's reviews ("pick up within 3 rings").

## UX principles

1. **Earn trust before asking.** Each permission is asked at the moment it's needed with one sentence
   on why. Only call screening is required.
2. **Never lose a call.** Every uncertain case rings the phone: forwarding not verified, policy not
   loaded, screening errors, a second SIM not set up.
3. **Show progress, not settings.** Onboarding is a 6-step guided path with a real test at the end and
   a "call your own assistant" demo.
4. **One tap from anywhere.** Reply, join, end, pause: from the notification or Quick Settings tile,
   without opening the app.
5. **Plain words.** Every screen says what will happen ("Your phone will ring. Answer it to talk to
   the caller.").

## Key flows

- **Onboarding:** Welcome → phone + OTP (auto-read) → name, languages, voice → permissions →
  forwarding codes per SIM → automatic test call → demo call → tips.
- **A screened call:** phone declines → carrier forwards → assistant answers → live notification
  updates with who/why/transcript → user replies or joins → summary with next steps.
- **Settings:** answering mode (assistant first / ring first / off), contacts screening, urgent
  pass-through, recording and retention, voice and languages, instructions and category rules,
  forwarding test / redo / turn off, plan, sign out and delete (both remove forwarding first).

## Plans

- **Trial:** everything for 7 days.
- **Free:** 15 assistant-answered calls a month with summaries; after that the assistant only takes
  messages until the next month.
- **Pro:** unlimited calls, live controls (transcript, replies, join), recordings, outbound calls.
  Equal charges ₹149–₹249; price Pro at or below that.

## What to measure

Forwarding verification rate, calls answered per active user, time to first spoken word, share of
calls with a caller name and reason captured, reply/join usage, eval pass rate, trial-to-paid conversion.
