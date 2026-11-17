"""Privacy policy and terms of service, served at /legal/privacy and /legal/terms.

Written for an India-first launch (Digital Personal Data Protection Act, 2023) and Google Play's
requirements. Company details come from LEGAL_* settings. Have a lawyer review before launch.
"""

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import get_settings

router = APIRouter(include_in_schema=False)

UPDATED = "17 November 2026"

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} · Pickup</title>
<style>
body{{font:16px/1.65 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:720px;margin:0 auto;padding:32px 20px;color:#1a1c22;background:#f8f6f1}}
h1{{font-size:30px;margin:0 0 4px}}h2{{font-size:19px;margin:32px 0 8px}}p,li{{color:#33363f}}.muted{{color:#6b6e78;font-size:14px}}
a{{color:#2747c9}}@media (prefers-color-scheme:dark){{body{{background:#111318;color:#e3e2e8}}p,li{{color:#c4c6d0}}a{{color:#b8c6ff}}}}
</style></head><body>{body}</body></html>"""


def _details() -> dict[str, str]:
    s = get_settings()
    return {
        "entity": escape(s.legal_entity_name),
        "email": escape(s.support_email),
        "officer": escape(s.grievance_officer),
        "address": escape(s.legal_address),
        "updated": UPDATED,
    }


PRIVACY = """
<h1>Privacy Policy</h1>
<p class="muted">Last updated {updated}</p>
<p>Pickup is an AI assistant that answers phone calls for you. This policy explains what we collect, why, who we share it with, and the choices you have. "We" means {entity}. "You" means the person who uses the Pickup app. "Callers" are the people who call you and speak with your assistant.</p>

<h2>1. What we collect</h2>
<ul>
<li><b>Account:</b> your mobile number, your name, your language and voice preferences.</li>
<li><b>Your device:</b> a push notification token, app version and Android version.</li>
<li><b>Contacts (only if you allow it):</b> names and phone numbers from your contacts, so people you know can ring through and your assistant can greet them by name.</li>
<li><b>Calls your assistant handles:</b> the caller's number, what the caller and your assistant said (a transcript), a summary, the reason for the call and suggested next steps. If call recording is on, an audio recording of the call.</li>
<li><b>Screening information:</b> when Pickup declines a call on your phone, it sends us the caller's number so the call can be matched when it reaches your assistant.</li>
<li><b>Your instructions and chats:</b> the instructions you give your assistant and your messages in the "Ask Pickup" chat.</li>
<li><b>Purchases:</b> subscription status from Google Play. We never see your card details.</li>
</ul>
<p>We do not read your SMS messages, your call history, your photos or your location.</p>

<h2>2. Why we use it</h2>
<ul>
<li>To answer calls for you, tell you who called and why, and let you reply or join live.</li>
<li>To make calls and set reminders when you ask the assistant to.</li>
<li>To keep the service secure, prevent abuse and fix problems.</li>
<li>To recognise spam: we keep a shared, anonymised count of how often a number is reported as spam and what it usually calls about. This uses a one-way hash of the number, never the number itself, and is never linked to you.</li>
</ul>
<p>We do not sell your data and we do not show ads.</p>

<h2>3. Callers</h2>
<p>Your assistant tells every caller at the start that it is an AI assistant and, when recording is on, that the call may be recorded. We process callers' voices and words only to provide the service to you. A caller may ask us to delete a recording of their voice by writing to {email}.</p>

<h2>4. Who processes data for us</h2>
<p>We use trusted providers who process data only on our instructions:</p>
<ul>
<li>Telephony providers (such as Exotel) to receive and connect calls.</li>
<li>Speech providers (such as Sarvam AI) to turn speech into text and text into speech.</li>
<li>Anthropic (Claude) to understand calls, write summaries and run the assistant.</li>
<li>Google Firebase for sign-in and notifications, and Google Play for subscriptions.</li>
<li>Our cloud hosting and storage providers.</li>
</ul>
<p>Some of these providers may process data outside India, with safeguards required by law.</p>

<h2>5. How long we keep it</h2>
<ul>
<li>Recordings: deleted automatically after the period you choose in settings (90 days by default).</li>
<li>Transcripts and summaries: until you delete the call or your account.</li>
<li>When you delete your account, we delete your data within 30 days, except what the law requires us to keep.</li>
</ul>

<h2>6. Your rights</h2>
<p>Under the Digital Personal Data Protection Act, 2023 you may access, correct or erase your data, withdraw consent, nominate someone to act for you, and raise a grievance. You can delete any call, turn off recording or delete your account in the app. For anything else, write to {email}.</p>

<h2>7. Security</h2>
<p>Data is encrypted in transit. Recordings are stored encrypted. Access is limited to people who need it to run the service.</p>

<h2>8. Children</h2>
<p>Pickup is not meant for anyone under 18, and we do not knowingly collect their data.</p>

<h2>9. Changes</h2>
<p>If we change this policy in a way that matters, we'll tell you in the app before it takes effect.</p>

<h2>10. Contact and grievance officer</h2>
<p>{entity}<br>{address}<br>Grievance officer: {officer}<br>Email: <a href="mailto:{email}">{email}</a></p>
"""

TERMS = """
<h1>Terms of Service</h1>
<p class="muted">Last updated {updated}</p>
<p>These terms are an agreement between you and {entity} for the Pickup app and service. By using Pickup you agree to them.</p>

<h2>1. Who can use Pickup</h2>
<p>You must be at least 18 and use a mobile number that belongs to you.</p>

<h2>2. What Pickup does</h2>
<p>Pickup declines calls you choose to screen, and your mobile carrier forwards them to an assistant number we give you. An AI assistant answers, talks to the caller, and sends you a transcript and summary. You can reply, join the call or end it. You can also ask the assistant to make calls for you.</p>

<h2>3. Call forwarding and carrier charges</h2>
<p>Pickup works through your carrier's call forwarding, which you switch on yourself by dialing codes. Your carrier may charge for forwarded calls under your plan. You are responsible for those charges and for switching forwarding off (the app shows you how) when you stop using Pickup.</p>

<h2>4. AI can make mistakes</h2>
<p>The assistant may mishear, misunderstand or summarise incorrectly. Check important details yourself. Pickup is not an emergency service: do not rely on it for emergencies, and it cannot contact emergency services for you.</p>

<h2>5. Your responsibilities</h2>
<ul>
<li>Use Pickup lawfully, including laws on call recording and consent where you and your callers are.</li>
<li>Don't use Pickup to harass, deceive or spam anyone, or for telemarketing.</li>
<li>Calls the assistant makes for you must be calls you could lawfully make yourself.</li>
<li>Keep your phone and account secure.</li>
</ul>

<h2>6. Plans and payments</h2>
<p>New accounts get a free trial. After it ends you can stay on the free plan, which has a monthly limit, or subscribe to Pickup Pro through Google Play. Subscriptions renew automatically until you cancel in Google Play. Refunds follow Google Play's policies.</p>

<h2>7. Ending the service</h2>
<p>You can delete your account at any time in the app. We may suspend accounts that break these terms or put others at risk.</p>

<h2>8. Disclaimers and liability</h2>
<p>Pickup is provided "as is". To the extent the law allows, we are not liable for indirect or consequential losses, or for missed or mishandled calls, and our total liability is limited to the amount you paid us in the 12 months before the claim.</p>

<h2>9. Changes</h2>
<p>We may update these terms. If a change matters, we'll tell you in the app before it applies.</p>

<h2>10. Law and disputes</h2>
<p>These terms are governed by the laws of India. Courts in {address_city} have jurisdiction.</p>

<h2>11. Contact</h2>
<p>{entity}<br>{address}<br>Email: <a href="mailto:{email}">{email}</a></p>
"""


@router.get("/legal/privacy", response_class=HTMLResponse)
async def privacy() -> HTMLResponse:
    return HTMLResponse(PAGE.format(title="Privacy Policy", body=PRIVACY.format(**_details())))


@router.get("/legal/terms", response_class=HTMLResponse)
async def terms() -> HTMLResponse:
    d = _details()
    d["address_city"] = escape(get_settings().legal_jurisdiction_city)
    return HTMLResponse(PAGE.format(title="Terms of Service", body=TERMS.format(**d)))
