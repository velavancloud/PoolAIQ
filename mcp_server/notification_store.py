"""
Standing in for a real SMS/push provider (Twilio, OneSignal, etc). Same
honesty principle as catalog_data.py: this is a stub, and the point isn't
to pretend it's a real Twilio integration — it's to prove the PROTOCOL
BOUNDARY. The reasoning engine (or anything calling the MCP server) should
never format an SMS body and call a provider SDK directly inline; it should
call one MCP tool, and swapping the stub for real Twilio later means
changing only this file, not every caller.

Notifications are appended to an in-memory list (module-level, reset on
process restart) — sufficient for a demo, explicitly not persistent.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SentNotification:
    id: str
    channel: str          # 'sms' or 'push'
    to: str
    body: str
    task_id: Optional[str]
    sent_at: str


_SENT_LOG: list = []
_counter = 0


def send_notification(channel: str, to: str, body: str, task_id: str = None) -> SentNotification:
    """
    The actual 'send'. In production this method's body is the only thing
    that changes to plug in Twilio/OneSignal/etc — everything upstream
    (the MCP tool definition, the reasoning engine's task creation) stays
    identical.
    """
    global _counter
    _counter += 1
    notif = SentNotification(
        id=f"notif_{_counter}",
        channel=channel,
        to=to,
        body=body,
        task_id=task_id,
        sent_at=datetime.now().isoformat(),
    )
    _SENT_LOG.append(notif)
    return notif


def get_sent_log() -> list:
    return list(_SENT_LOG)


if __name__ == "__main__":
    n = send_notification(
        channel="sms",
        to="+1-704-555-0100",
        body="PoolAIQ: Add 8oz muriatic acid near return jets, pump running. Reply DONE when complete.",
        task_id="task_demo_1",
    )
    print(f"Sent: {n}")
    print(f"Log now has {len(get_sent_log())} entries")
