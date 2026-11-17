"""Sync configuration from GitHub into Fly.io secrets before a deploy.

- Values provided as GitHub secrets/variables (passed in as environment variables) are set.
- JWT_SECRET, ADMIN_TOKEN and TELEPHONY_WEBHOOK_SECRET are generated once if Fly doesn't have them.
- PUBLIC_BASE_URL is always https://<app>.fly.dev unless you set your own.
"""

import json
import os
import secrets
import subprocess
import sys

app = os.environ["APP"]
listed = subprocess.run(["flyctl", "secrets", "list", "--app", app, "--json"], capture_output=True, text=True, check=True)
existing = {item.get("Name") or item.get("name") for item in json.loads(listed.stdout or "[]")}

values: dict[str, str] = {}
rotate_webhook = os.environ.get("ROTATE_WEBHOOK_SECRET") == "true"
for name in ("JWT_SECRET", "ADMIN_TOKEN", "TELEPHONY_WEBHOOK_SECRET"):
    if name not in existing or (rotate_webhook and name == "TELEPHONY_WEBHOOK_SECRET"):
        values[name] = secrets.token_urlsafe(48)

passthrough = [
    "ANTHROPIC_API_KEY", "SARVAM_API_KEY", "DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY", "CARTESIA_API_KEY",
    "FIREBASE_PROJECT_ID", "FCM_SERVICE_ACCOUNT_JSON", "BETA_LOGIN_NUMBERS", "BETA_LOGIN_CODE",
    "TELEPHONY_PROVIDER", "EXOTEL_ACCOUNT_SID", "EXOTEL_API_KEY", "EXOTEL_API_TOKEN", "EXOTEL_SUBDOMAIN",
    "EXOTEL_OUTBOUND_FLOW_ID", "PLIVO_AUTH_ID", "PLIVO_AUTH_TOKEN", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
    "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", "LEGAL_ENTITY_NAME", "LEGAL_ADDRESS", "LEGAL_JURISDICTION_CITY",
    "SUPPORT_EMAIL", "GRIEVANCE_OFFICER", "PUBLIC_BASE_URL",
    "APNS_KEY_P8", "APNS_KEY_ID", "APPLE_TEAM_ID", "IOS_BUNDLE_ID",
]
for name in passthrough:
    value = os.environ.get(name, "").strip()
    if value:
        values[name] = value
values.setdefault("PUBLIC_BASE_URL", f"https://{app}.fly.dev")

if not values:
    print("No secret changes")
    sys.exit(0)
args = ["flyctl", "secrets", "set", "--stage", "--app", app] + [f"{k}={v}" for k, v in values.items()]
subprocess.run(args, check=True, stdout=subprocess.DEVNULL)
print("Staged secrets:", ", ".join(sorted(values)))
