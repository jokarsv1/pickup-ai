"""Structured outputs the model fills in during and after a call."""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["delivery", "bank_finance", "sales", "recruiter", "appointment", "personal", "government", "scam", "survey", "other"]
Urgency = Literal["low", "normal", "high"]


class LiveIntent(BaseModel):
    """What the user's phone shows while the assistant is still talking to the caller."""

    caller_name: str | None = Field(None, description="The caller's own name if they said it")
    organisation: str | None = Field(None, description="Company or organisation the caller represents, if any")
    category: Category = "other"
    reason: str = Field(..., description="Why they are calling, in at most 12 words, e.g. 'Parcel at the gate, needs OTP'")
    urgency: Urgency = "normal"
    is_spam: bool = False
    suggested_replies: list[str] = Field(
        default_factory=list,
        description="Up to 3 short replies the user might want relayed, written as the user would say them, "
        "e.g. 'Leave it with the security guard'. Empty if nothing useful.",
    )


class SuggestedAction(BaseModel):
    type: Literal["reminder", "call_back", "save_contact", "block"]
    title: str = Field(..., description="Short label for a button, e.g. 'Call back Rahul from HDFC'")
    due_at: str | None = Field(None, description="ISO-8601 datetime with timezone for reminders, if a time was mentioned")
    number: str | None = Field(None, description="Phone number for call_back or save_contact, if different from the caller's")
    contact_name: str | None = Field(None, description="Name to save for save_contact")


class CallInsights(BaseModel):
    caller_name: str | None = None
    organisation: str | None = None
    category: Category = "other"
    reason: str = Field(..., description="Why they called, at most 12 words")
    summary: str = Field(..., description="Two or three plain sentences: who called, why, and what was agreed or left as a message")
    urgency: Urgency = "normal"
    is_spam: bool = False
    actions: list[SuggestedAction] = Field(default_factory=list, description="At most 3 useful next steps for the user")
