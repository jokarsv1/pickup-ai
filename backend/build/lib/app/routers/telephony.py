"""Webhooks and media streams from the telephony provider. Not part of the public API."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, status
from fastapi.responses import JSONResponse
from loguru import logger
from pipecat.runner.utils import parse_telephony_websocket
from sqlalchemy import select

from app.config import get_settings
from app.db import sessionmaker
from app.models import Call, Line, OutboundTask
from app.services import calls as call_service
from app.services.calls import route_inbound
from app.telephony.base import media_token, media_ws_url, verify_media_token
from app.telephony.plivo import PlivoProvider
from app.telephony.registry import get_provider
from app.voice.session import run_call, run_notice

router = APIRouter(prefix="/telephony", include_in_schema=False)

NOTICES = {
    "verified": "Your Pickup assistant is set up. You can hang up now.",
    "reject_loop": "Sorry, they're not able to join right now. Goodbye.",
    "unknown_number": "Sorry, this number is not in service.",
    "verify_answered": "This is Pickup testing your call forwarding. You can hang up now.",
}
FAILED_STATUSES = {"busy", "no-answer", "failed", "canceled", "noanswer", "rejected", "timeout"}


async def _params(request: Request) -> dict[str, Any]:
    params: dict[str, Any] = dict(request.query_params)
    if request.method == "POST":
        try:
            form = await request.form()
            params.update({k: v for k, v in form.items() if isinstance(v, str)})
        except Exception:
            pass
    return params


def _check_token(call_id: str, token: str) -> None:
    if not verify_media_token(call_id, token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bad token")


def _check_secret(secret: str) -> None:
    if secret != get_settings().telephony_webhook_secret:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bad secret")


@router.post("/{provider}/inbound")
async def inbound(provider: str, request: Request) -> Response:
    if provider not in ("twilio", "plivo"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    p = get_provider(provider)
    params = await _params(request)
    if not await p.validate(request, params):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid signature")
    info = p.parse_inbound(params)
    async with sessionmaker()() as session:
        decision = await route_inbound(
            session, provider=provider, provider_call_id=info.provider_call_id, from_raw=info.from_number, to_raw=info.to_number
        )
    if decision.kind == "agent" and decision.call_id:
        return p.stream_response(decision.call_id)
    return p.say_and_hangup(decision.say or "Goodbye.")


@router.post("/{provider}/answer/{call_id}/{token}")
async def outbound_answered(provider: str, call_id: str, token: str, request: Request) -> Response:
    _check_token(call_id, token)
    p = get_provider(provider)
    params = await _params(request)
    if not await p.validate(request, params):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid signature")
    if call_id.startswith("verify-"):
        return p.say_and_hangup(NOTICES["verify_answered"])
    info = p.parse_inbound(params)
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None:
            return p.say_and_hangup("Goodbye.")
        if info.provider_call_id:
            call.provider_call_id = info.provider_call_id
        await session.commit()
    return p.stream_response(call_id)


async def _handle_status(call_id: str, call_status: str) -> None:
    if call_id.startswith("verify-") or call_status not in FAILED_STATUSES:
        return
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        if call is None or call.state != "ringing":
            return
        call.state = "failed"
        call.end_reason = call_status
        if call.outbound_task_id:
            task = await session.get(OutboundTask, call.outbound_task_id)
            if task:
                from datetime import timedelta

                from app.db import utcnow

                if task.attempts < 3:
                    task.state = "scheduled"
                    task.scheduled_at = utcnow() + timedelta(minutes=10)
                else:
                    task.state = "failed"
                    task.result_summary = "Nobody picked up."
        await session.commit()
        user_id = call.user_id
    await call_service.notify(user_id, {"type": "outbound.updated", "call_id": call_id})


@router.post("/{provider}/status/{call_id}/{token}")
async def call_status(provider: str, call_id: str, token: str, request: Request) -> Response:
    _check_token(call_id, token)
    params = await _params(request)
    raw = (params.get("CallStatus") or params.get("Status") or params.get("HangupCause") or "").lower().replace("_", "-")
    await _handle_status(call_id, raw)
    return Response(status_code=204)


@router.post("/plivo/transfer/{call_id}/{token}")
async def plivo_transfer(call_id: str, token: str) -> Response:
    _check_token(call_id, token)
    async with sessionmaker()() as session:
        call = await session.get(Call, call_id)
        line = await session.get(Line, call.line_id) if call and call.line_id else None
    provider = get_provider("plivo")
    if line is None or not isinstance(provider, PlivoProvider):
        return provider.say_and_hangup("Sorry, we couldn't connect you. Goodbye.")
    return provider.dial_response(line.phone_e164, line.assistant_number)


# ---------------------------------------------------------------------------- Exotel
@router.api_route("/exotel/{secret}/voicebot", methods=["GET", "POST"])
async def exotel_voicebot(secret: str, request: Request) -> JSONResponse:
    """Voicebot applet dynamic URL: returns the WebSocket to stream to."""
    _check_secret(secret)
    params = await _params(request)
    custom = params.get("CustomField")
    if custom and custom.startswith("call_"):
        return JSONResponse({"url": media_ws_url(custom)})
    return JSONResponse({"url": media_ws_url("exotel-new")})


async def _call_by_provider_id(provider_call_id: str | None) -> Call | None:
    if not provider_call_id:
        return None
    async with sessionmaker()() as session:
        return await session.scalar(select(Call).where(Call.provider_call_id == provider_call_id).order_by(Call.started_at.desc()))


@router.api_route("/exotel/{secret}/passthru", methods=["GET", "POST"])
async def exotel_passthru(secret: str, request: Request) -> Response:
    """After the bot: 200 sends the call to the Connect applet (user joins), 302 ends it."""
    _check_secret(secret)
    params = await _params(request)
    call = await _call_by_provider_id(params.get("CallSid"))
    return Response(status_code=200 if call and call.takeover_requested else 302)


@router.api_route("/exotel/{secret}/connect", methods=["GET", "POST"])
async def exotel_connect(secret: str, request: Request) -> JSONResponse:
    _check_secret(secret)
    params = await _params(request)
    call = await _call_by_provider_id(params.get("CallSid"))
    if call is None or not call.line_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    async with sessionmaker()() as session:
        line = await session.get(Line, call.line_id)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return JSONResponse(
        {
            "fetch_after_attempt": False,
            "destination": {"numbers": [line.phone_e164]},
            "outgoing_phone_number": line.assistant_number,
            "record": False,
            "max_ringing_duration": 30,
            "max_conversation_duration": 3600,
            "music_on_hold": {"type": "operator_tone"},
        }
    )


@router.api_route("/exotel/{secret}/status", methods=["GET", "POST"])
async def exotel_status(secret: str, request: Request) -> Response:
    _check_secret(secret)
    params = await _params(request)
    call_id = params.get("CustomField") or ""
    if call_id.startswith("call_"):
        await _handle_status(call_id, (params.get("Status") or "").lower())
    return Response(status_code=204)


# ---------------------------------------------------------------------------- Media stream
@router.websocket("/media/{call_id}/{token}")
async def media(websocket: WebSocket, call_id: str, token: str) -> None:
    if not verify_media_token(call_id, token):
        await websocket.close(code=4403)
        return
    await websocket.accept()
    try:
        transport_type, call_data = await parse_telephony_websocket(websocket)
    except ValueError:
        logger.warning("Media stream closed before start")
        return

    if call_id == "exotel-new":
        existing = await _call_by_provider_id(call_data.get("call_id"))
        if existing is not None:
            call_id = existing.id
        else:
            async with sessionmaker()() as session:
                decision = await route_inbound(
                    session,
                    provider="exotel",
                    provider_call_id=call_data.get("call_id"),
                    from_raw=call_data.get("from"),
                    to_raw=call_data.get("to"),
                )
            if decision.kind != "agent" or not decision.call_id:
                await run_notice(websocket, transport_type, call_data, decision.say or "Goodbye.")
                return
            call_id = decision.call_id
    else:
        async with sessionmaker()() as session:
            call = await session.get(Call, call_id)
            if call is None:
                await websocket.close()
                return
            if not call.provider_call_id and call_data.get("call_id"):
                call.provider_call_id = call_data.get("call_id")
                await session.commit()
    await run_call(websocket, call_id, transport_type, call_data)


__all__ = ["router", "media_token"]
