#!/usr/bin/env python
"""
wake.py - inject a USER-STYLE message into an EXISTING mcode session.

WHY THIS EXISTS. The heartbeat was built wrong. `mcode exec --cwd <root>` does not
wake the agent - it SPAWNS A NEW, headless session that runs an agent nobody sees.
That is why "dispara, trabalha" was true and "manda-te mensagem" was false: they
are two different mechanisms and only the wrong one was wired.

The runtime already has the RIGHT mechanism, and the runtime itself named it.
When an exec is refused with "Session already has an active Turn", the message
says: "Use queue send to deliver the message after it." `queue send` is not a CLI
subcommand; it is the row in local_runtime_queue_items. MEASURED by reading a real
queued item: it carries a userMessageId and a `message.content` - i.e. it IS a
user message, delivered when the current turn ends. Exactly "like a user".

USAGE
    python wake.py <session_id> <message_file>
    python wake.py <session_id> --test
"""

import sqlite3
import json
import sys
import time
import uuid
import os

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
AGENT = "mavis"
MODEL = {
    "provider_id": "minimax",
    "model_id": "MiniMax-M3.1-Flash-Preview",
    "reasoning": True,
    "context_limit": 512000,
    "thinking": {"effort": "max"},
    "parameterSnapshot": {"context": "default", "effort": "selection"},
}


def now_ms():
    return int(time.time() * 1000)


def enqueue(session_id, content, source="heartbeat", model=None):
    item_id = "queue_" + str(uuid.uuid4())
    user_msg_id = "msg-user-v1-" + "".join(
        __import__("secrets").choice(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        ) for _ in range(43)
    )
    client_request_id = "minimax-code_hb_" + uuid.uuid4().hex[:12]
    data = {
        "itemId": item_id,
        "userMessageId": user_msg_id,
        "sessionId": session_id,
        "agentName": AGENT,
        "source": source,
        "status": "queued",
        "message": {"content": content, "attachments": []},
        "model": model or MODEL,
        "createdAt": now_ms(),
        "clientRequestId": client_request_id,
        "deliveryAttempts": [],
    }
    conn = sqlite3.connect(DB, timeout=15)
    try:
        conn.execute(
            "INSERT INTO local_runtime_queue_items "
            "(session_id, item_id, status, created_at_ms, data_json, source, "
            " client_request_id, dedupe_key) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                session_id,
                item_id,
                "queued",
                now_ms(),
                json.dumps(data),
                source,
                client_request_id,
                "hb-" + str(now_ms()),  # dedupe: one wake per enqueue
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return item_id


def pending(session_id):
    conn = sqlite3.connect(DB, timeout=15)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM local_runtime_queue_items "
            "WHERE session_id=? AND status='queued'",
            (session_id,),
        ).fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)

    if len(sys.argv) == 2:
        # status mode: how many wakes are waiting for a session
        print("queued for %s: %d" % (sys.argv[1], pending(sys.argv[1])))
        sys.exit(0)

    session_id = sys.argv[1]
    if sys.argv[2] == "--test":
        content = ("HEARTBEAT WAKE TEST. If you are reading this as a USER message "
                   "in this session, the injection path works: the heartbeat can "
                   "now wake the agent that is already talking to the owner, "
                   "instead of spawning a headless session nobody sees. "
                   "Reply with one short line confirming.")
    else:
        with open(sys.argv[2], "r", encoding="utf-8") as fh:
            content = fh.read()

    iid = enqueue(session_id, content)
    print("queued %s -> %s (pending now: %d)" % (iid, session_id, pending(session_id)))
