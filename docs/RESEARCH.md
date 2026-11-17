# Research notes and decisions

Checked on 16-17 November 2026. Each decision lists its source.

## Platform

| Finding | Decision | Source |
|---|---|---|
| The screening app sees calls from contacts only if it holds `READ_CONTACTS`; it must answer within 5 seconds; `Call.Details` has no SIM (account handle) | Ask for contacts (optional), keep all screening local and fast, require forwarding on every active SIM | developer.android.com/reference/android/telecom/CallScreeningService |
| `setRejectCall` disconnects "as if the user had manually rejected it" | Declining triggers the carrier's forward-when-busy | CallScreeningService.CallResponse.Builder reference |
| `ACTION_CALL` only dials call-forwarding codes for the default dialer; others get `ACTION_DIAL` behaviour | Open the dialer with each code filled in; user taps Call | AOSP `Intent.ACTION_CALL` docs; home-assistant/android#5208 |
| Google Play requires target API 36 from 31 Aug 2026 | `targetSdk = 36` | support.google.com/googleplay/android-developer/answer/11926878 |
| Android 16 Live Updates: `setRequestPromotedOngoing`, `setShortCriticalText` in androidx.core 1.17+; BigText/Call/Progress styles only | Live call notification uses BigTextStyle and requests promotion | developer.android.com/develop/ui/compose/notifications/live-update |
| AGP 9 has built-in Kotlin; the `kotlin-android` plugin must not be applied; AGP 9.5 needs Gradle 9.6+ and JDK 17 | AGP 9.5.1, Gradle 9.9.1, Kotlin 2.4.21 via buildscript classpath, Compose compiler plugin | AGP 9.0 and 9.5 release notes; kotlinlang.org Compose compiler guide |
| Play Billing 8 removed `enablePendingPurchases()` without params and changed the product details listener | Billing 9.1 with `PendingPurchasesParams` and `enableAutoServiceReconnection()` | developer.android.com/google/play/billing/release-notes |

Library versions: Compose BOM 2026.09.00 (Material 3 1.4.0), core-ktx 1.19.1, activity-compose 1.13.0,
lifecycle 2.11.0, navigation-compose 2.10.2, DataStore 1.3.0, OkHttp 5.5.1, kotlinx-serialization
1.13.0, coroutines 1.11.0, Firebase BoM 35.2.0, google-services 4.6.0.

## India

| Finding | Decision | Source |
|---|---|---|
| Twilio can't place domestic India-to-India calls | Exotel default for India; Plivo and Twilio adapters for other markets | exotel.com/blog/voice-call-api-in-india |
| Exotel AgentStream: Voicebot applet streams 8 kHz PCM over WebSocket; its URL can be an endpoint returning the WSS URL; the start message carries `from` and `to` | Route the call when the stream starts | developer.exotel.com/docs/agentstream |
| Exotel Connect applet accepts a dynamic URL returning numbers to dial | Take over = Passthru (200) → Connect to the user's number | docs.exotel.com programmable-connect |
| From 1 July 2026 carriers SMS users when forwarding is activated | Onboarding warns users to expect the SMS | Bank and police advisories, July 2026 |
| Equal's App Store reviews report a carrier announcement on forwarded calls that makes callers hang up | Greeting starts instantly; track abandon rate; market risk noted in PRODUCT.md | apps.apple.com Equal AI reviews |

## Voice AI

| Finding | Decision | Source |
|---|---|---|
| Pipecat 1.16 defaults to VAD start + Smart Turn v3 stop strategies; `PipelineWorker` and `WorkerRunner` replace the deprecated task/runner | Default turn strategies with Silero VAD | Installed pipecat-ai 1.16.0 source |
| Pipecat's Anthropic service knows Claude 5 models (effort low for `claude-opus-5-5`) and keeps thinking blocks in context | Use `AnthropicLLMService` with prompt caching | Installed pipecat-ai source |
| Sarvam Saaras V3 leads IndicVoices WER and supports code-mixed streaming; Bulbul V3 is the current TTS (V2 deprecated) | `saaras:v3-realtime` in codemix mode, `bulbul:v3` | sarvam.ai/models; Business Standard, Feb 2026 |
| Claude API: server-side refusal fallbacks (`fallbacks: "default"`), structured outputs via `messages.parse` | Used for summaries, live intent and chat | Anthropic SDK 2.9 and API docs |

## Competitors

- **Equal AI:** Android (caller ID role) and iPhone (call forwarding). Features: live transcript,
  summaries, recordings, take over, instruction packs, outbound calls, reminders. Gold plan ₹149–₹249.
- **Truecaller Assistant:** AI call screening with voice choice, bundled with caller ID and spam blocking.
- **Google Call Screen (Pixel)** and **Apple Call Screening (iOS 26):** free, built-in, but they ask
  for a name and reason and don't hold a real conversation or act on instructions.
