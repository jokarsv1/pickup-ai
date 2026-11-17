"""Chat with the assistant, outbound calls, billing and the live event stream."""

import asyncio
import contextlib
import json
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from loguru import logger
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.ai.assistant import chat as run_chat
from app.config import get_settings
from app.db import utcnow
from app.deps import CurrentUser, Session
from app.entitlements import entitlement_for
from app.events import bus, user_topic
from app.models import ChatMessage, OutboundTask, Purchase
from app import ratelimit
from app.phone import normalize
from app.services.outbound import outbound_problem
from app.schemas import ChatIn, ChatMessageOut, ChatReply, EntitlementOut, OutboundIn, OutboundOut, PlayPurchaseIn
from app.security import AuthError, decode_ws_ticket

router = APIRouter(prefix="/v1")


def chat_out(m: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut(id=m.id, role=m.role, text=m.text, client_actions=m.client_actions or [], at=m.created_at)


@router.get("/assistant/chat", response_model=list[ChatMessageOut])
async def chat_history(session: Session, user: CurrentUser, limit: int = Query(50, ge=1, le=200)) -> list[ChatMessageOut]:
    rows = (
        await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.user_id == user.id, ChatMessage.role.in_(("user", "assistant")), ChatMessage.text != "")
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
    ).all()
    return [chat_out(m) for m in reversed(rows)]


@router.post("/assistant/chat", response_model=ChatReply)
async def chat(body: ChatIn, session: Session, user: CurrentUser) -> ChatReply:
    ratelimit.check(f"chat:{user.id}", limit=30, window_seconds=600)
    reply, actions = await run_chat(session, user, body.text.strip())
    history = await chat_history(session, user, limit=50)
    return ChatReply(reply=reply, client_actions=actions, messages=history)


def outbound_out(t: OutboundTask) -> OutboundOut:
    return OutboundOut(
        id=t.id,
        to_number=t.to_number,
        to_name=t.to_name,
        goal=t.goal,
        scheduled_at=t.scheduled_at,
        state=t.state,
        call_id=t.call_id,
        result_summary=t.result_summary,
    )


@router.post("/outbound", response_model=OutboundOut)
async def create_outbound(body: OutboundIn, session: Session, user: CurrentUser) -> OutboundOut:
    ent = await entitlement_for(session, user)
    if not ent.outbound_calls:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Calls made by your assistant are part of Pickup Pro")
    number = normalize(body.to_number)
    if not number:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid phone number")
    problem = await outbound_problem(session, user.id, number)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    when = body.scheduled_at or utcnow()
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    task = OutboundTask(user_id=user.id, to_number=number, to_name=body.to_name, goal=body.goal.strip(), scheduled_at=when)
    session.add(task)
    await session.commit()
    return outbound_out(task)


@router.get("/outbound", response_model=list[OutboundOut])
async def list_outbound(session: Session, user: CurrentUser) -> list[OutboundOut]:
    rows = (await session.scalars(select(OutboundTask).where(OutboundTask.user_id == user.id).order_by(OutboundTask.scheduled_at.desc()).limit(50))).all()
    return [outbound_out(t) for t in rows]


@router.delete("/outbound/{task_id}", status_code=204)
async def cancel_outbound(task_id: str, session: Session, user: CurrentUser) -> None:
    task = await session.get(OutboundTask, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if task.state == "scheduled":
        task.state = "cancelled"
        await session.commit()


async def _verify_play_subscription(product_id: str, token: str) -> dict:
    """Google Play Developer API: purchases.subscriptionsv2.get."""
    s = get_settings()
    if not (s.google_play_service_account_json or s.google_play_service_account_file):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Purchases can't be verified on this server yet")
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    scopes = ["https://www.googleapis.com/auth/androidpublisher"]
    if s.google_play_service_account_json:
        creds = service_account.Credentials.from_service_account_info(json.loads(s.google_play_service_account_json), scopes=scopes)
    else:
        creds = service_account.Credentials.from_service_account_file(s.google_play_service_account_file, scopes=scopes)
    await run_in_threadpool(creds.refresh, Request())
    url = (
        "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
        f"{s.google_play_package_name}/purchases/subscriptionsv2/tokens/{token}"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {creds.token}"})
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google Play didn't accept that purchase")
    return resp.json()


@router.post("/billing/google-play", response_model=EntitlementOut)
async def google_play_purchase(body: PlayPurchaseIn, session: Session, user: CurrentUser) -> EntitlementOut:
    if body.product_id not in get_settings().play_pro_product_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown product")
    data = await _verify_play_subscription(body.product_id, body.purchase_token)
    state = data.get("subscriptionState", "")
    expiry = None
    for item in data.get("lineItems", []):
        if item.get("expiryTime"):
            candidate = datetime.fromisoformat(item["expiryTime"].replace("Z", "+00:00"))
            expiry = max(expiry, candidate) if expiry else candidate
    purchase = await session.scalar(select(Purchase).where(Purchase.purchase_token == body.purchase_token))
    if purchase is None:
        purchase = Purchase(user_id=user.id, product_id=body.product_id, purchase_token=body.purchase_token, state=state)
        session.add(purchase)
    elif purchase.user_id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This purchase belongs to another account")
    purchase.state = state
    purchase.expires_at = expiry
    purchase.raw = data
    if state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD") and expiry:
        user.plan = "pro"
        user.plan_expires_at = expiry
    await session.commit()
    ent = await entitlement_for(session, user)
    return EntitlementOut(**ent.__dict__)


@router.websocket("/stream")
async def stream(websocket: WebSocket, ticket: str) -> None:
    """Live events for the signed-in user: call started, transcript, intent, summary..."""
    try:
        user_id = decode_ws_ticket(ticket)
    except AuthError:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    async with bus.subscribe(user_topic(user_id)) as queue:

        async def pump() -> None:
            while True:
                event = await queue.get()
                await websocket.send_json(event)

        sender = asyncio.create_task(pump())
        try:
            while True:
                message = await websocket.receive_text()
                if message == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug(f"Stream closed: {exc}")
        finally:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await sender
