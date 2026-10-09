#!/usr/bin/env python3
"""Wake/queue/cron surgery for the mcode runtime store.

Modes
  status      read-only census: queue rows for a session, the cron facts
  repair      rewrite ONE corrupt queue row into the shape the runtime
              itself writes (adds requestedTurnId + routing_fingerprint,
              drops the unknown deliveryAttempts key).  Backs up first.
  inject      insert a NEW valid queue row for a session, using a
              runtime-written row from the same session as the template.
  arm-cron    create ONE runtime cron + scheduler job (sessionTargetMode
              = sessionId) with next_run_at_ms = now + delay.
  prune       remove queued rows that have sat unclaimed past --stale-mins.
              --all-sessions widens it to orphans in EVERY session (D-5).
  cron-alarm  D-2 + D-4: rc=3 when the runtime's own cron scheduler has
              produced no run for > 15 min while a cron is armed+active.
  wake-plan   D-7: print the transport decision (exec vs queue) computed from
              the signals that were MEASURED to predict acceptance, plus the
              session's own workspace_dir. `status` is reported but never
              decides -- it was a false negative on 2 of 2 refusals.

Design rules taken from measured evidence, not assumption:
  * the runtime DOES read the queue (it answered with "Queue row is
    corrupt: <session>/<item>" naming our own item) -- so injection is a
    real channel, it was only malformed;
  * a runtime-written row carries requestedTurnId and routing_fingerprint;
    our hand-written one carried neither, which is the whole difference;
  * every mutation writes a JSON backup next to this file first.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# SOTTO_WAKE_DB / SOTTO_WAKE_BACKUP_DIR exist so a gate can drive THIS FILE
# against a throwaway store.  Without them the wedge can only be demonstrated
# by re-implementing the predicate in the gate's own python -- which is what
# the previous audit did, and which proves the gate's copy of the predicate
# rather than the shipped one.  Default is unchanged: the live runtime store.
DB = os.environ.get("SOTTO_WAKE_DB") or \
    r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
BACKUP_DIR = os.environ.get("SOTTO_WAKE_BACKUP_DIR") or \
    os.path.dirname(os.path.abspath(__file__))
BROKEN = "queue_ec7ae0a0-d5ad-44a4-9d53-7a824dc2d162"

# --- D-1: the shape of a runtime-minted userMessageId -------------------------
# MEASURED 12:58 (POP = 20 most recent role='user' rows, whole-table filter):
# 19 of 20 are length 55; the 1 exception is one of OUR rows (length 48).
#   prefix 'msg-user-v1-' = 12 chars + 43 chars of base64url that decode to
#   exactly 32 bytes.  So the shape is 12 + token_urlsafe(32).
# The old mint was f"msg-user-v1-wake{uuid4().hex[:32]}" = 48 chars, hex
# alphabet.  IT IS NOT THE CAUSE of any delivery failure -- see receipt-24
# for the measurement that proves it -- but an id the runtime never produces
# cannot be deduped by anything that assumes the runtime's own shape.
USER_MESSAGE_ID_PREFIX = "msg-user-v1-"
USER_MESSAGE_ID_BODY_CHARS = 43          # == len(token_urlsafe(32))
USER_MESSAGE_ID_LENGTH = len(USER_MESSAGE_ID_PREFIX) + USER_MESSAGE_ID_BODY_CHARS

# --- D-4: how stale a cron scheduler may be before it is an outage -----------
# The audit's threshold.  Measured on this store: the newest cron run is
# 2026-10-06 10:11:00, so the alarm fires on a ~26.7 h outage.
CRON_ALARM_MIN_MS = 15 * 60_000

ROUTING_API = ('queue-routing/v1:[["source","api"],["platform",null],'
               '["client",null],["agent","mavis"],["agentBinding",null],'
               '["binding",null],["channel",null],["channelId",null],'
               '["thread",null],["chat",null],["scope",null],'
               '["chatType",null],["sender",null]]')


def now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")


def local(ms) -> str:
    if ms in (None, ""):
        return "None"
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return repr(ms)


def out(*a) -> None:
    print(*a, flush=True)


def mint_user_message_id() -> str:
    """D-1.  Mint an id in the SHAPE the runtime writes.

    Deliberately NOT the audit's literal suggestion ("copy userMessageId from
    the template unchanged, like every other field"): `d = dict(tpl)` already
    does that for every other field, and copying this one verbatim would give
    every wake the SAME id as the template row -- a collision is strictly worse
    than a wrong alphabet.  What is asked for is the shape; identity stays
    unique.
    """
    body = secrets.token_urlsafe(32)
    assert len(body) == USER_MESSAGE_ID_BODY_CHARS, len(body)
    return USER_MESSAGE_ID_PREFIX + body


def cron_fields(expression: str | None) -> list[str]:
    """A cron expression is FIVE whitespace-separated fields.

    D-2, MEASURED: the shipped query was
        where j.schedule_json like '%* * * * *%'
    which wants FIVE literal stars.  Real expressions on this store are
    "*/3 * * * *" and "2,9,16,23,30,37,44,51 * * * *" -- FOUR trailing stars
    -- so the query returns 0 rows against 30 scheduler jobs and the status
    tool printed an EMPTY cron section, hiding the very outage D-4 alarms on.
    The audit's proposed replacement, like '%* * * *', ALSO returns 0 rows:
    a LIKE without a trailing % must match to end-of-string, and these rows
    end in '"America/Sao_Paulo"}'.  Both star patterns are wrong.  Count the
    FIELDS, which is what "is this a cron" actually means.
    """
    return (expression or "").split()


def cron_health(con: sqlite3.Connection, now_ms: int) -> dict:
    """The ONE cron alarm.  D-2 and D-4 are the same hookup, by design.

    Alarm when  now - max(cron_runs.created_at_ms) > 15 min  WHILE  a row
    exists with  cron_definitions.deleted_at_ms IS NULL  joined to a
    state='active' scheduler job.  Both halves matter: a store with no crons
    armed is not dead, and a dead scheduler with nothing armed is harmless.
    """
    newest = con.execute(
        "select max(created_at_ms) from local_runtime_v2_cron_runs").fetchone()[0]
    armed = con.execute(
        "select count(*) from local_runtime_v2_cron_definitions d "
        "join local_runtime_v2_scheduler_jobs j "
        "on j.scheduler_id = d.scheduler_id "
        "where d.deleted_at_ms is null and j.state='active'").fetchone()[0]
    if newest in (None, ""):
        age_ms = None
    else:
        age_ms = now_ms - int(newest)
    alarming = armed > 0 and (age_ms is None or age_ms > CRON_ALARM_MIN_MS)
    return {"newest_ms": newest, "newest_local": local(newest),
            "age_ms": age_ms, "age_min": None if age_ms is None else age_ms / 60000.0,
            "armed": armed, "alarming": alarming,
            "threshold_min": CRON_ALARM_MIN_MS / 60000.0}


def report_cron_health(h: dict, prefix: str = "CRON-HEALTH") -> None:
    age = "NEVER-RUN" if h["age_min"] is None else f"{h['age_min']:.1f}min"
    verdict = "ALARM" if h["alarming"] else "ok"
    out(f"  {prefix} verdict={verdict} newest_run={h['newest_local']} "
        f"age={age} armed_active_crons={h['armed']} "
        f"threshold={h['threshold_min']:.0f}min")


def backup(name: str, payload: dict) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    p = os.path.join(BACKUP_DIR, f"backup-{stamp}-{name}.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return p


def open_rw() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    return con


def template_from(con: sqlite3.Connection, session_id: str,
                  fallback_session: str | None = None) -> dict:
    """A runtime-written row = the authoritative shape.

    Preferred: one for the SAME session.  If the session has never received a
    queued item (POPULATION = 0 such rows) we fall back to any runtime-written
    row, and say so loudly -- the shape differs only by sessionId/userMessageId.
    """
    row = con.execute(
        "select session_id, data_json from local_runtime_queue_items "
        "where session_id=? and routing_fingerprint is not null "
        "order by rowid desc limit 1", (session_id,)).fetchone()
    if row is not None:
        return json.loads(row["data_json"])

    probe = None
    if fallback_session:
        probe = con.execute(
            "select session_id, data_json from local_runtime_queue_items "
            "where session_id=? and routing_fingerprint is not null "
            "order by rowid desc limit 1", (fallback_session,)).fetchone()
    if probe is None:
        probe = con.execute(
            "select session_id, data_json from local_runtime_queue_items "
            "where routing_fingerprint is not null "
            "order by rowid desc limit 1").fetchone()
    if probe is None:
        raise SystemExit(
            "NO TEMPLATE ANYWHERE: no runtime-written queue row exists in this "
            "store. Refusing to invent a shape -- inventing the shape is "
            "exactly what produced the corrupt row.")
    out(f"  NOTE: session {session_id} has 0 runtime-written queue rows; "
        f"template borrowed from session {probe['session_id']}")
    return json.loads(probe["data_json"])


def cmd_status(args) -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out(f"[{now()}] STATUS (read-only)  session={args.session}")
    out("\n-- queue rows for this session --")
    out(f"   (POPULATION = whole table = {con.execute('select count(*) from local_runtime_queue_items').fetchone()[0]} rows)")
    for r in con.execute(
            "select item_id, status, source, claim_id, routing_fingerprint, "
            "created_at_ms, data_json from local_runtime_queue_items "
            "where session_id=? order by rowid desc", (args.session,)):
        d = json.loads(r["data_json"])
        out(f"  item={r['item_id']}")
        out(f"    status={r['status']} source={r['source']} claim={r['claim_id']} "
            f"created={local(r['created_at_ms'])}")
        out(f"    routing_fingerprint={'SET' if r['routing_fingerprint'] else 'NULL'}")
        out(f"    data_json keys={sorted(d.keys())}")
        out(f"    content={d.get('message', {}).get('content', '')[:110]!r}")

    out("\n-- cron: every CRON-EXPRESSION job (5 fields) and its staleness --")
    out("   (D-2: the old 'like %* * * * *%' matched 0 of 30 jobs; a real")
    out("    expression has FOUR trailing stars, and 'like %* * * *' with no")
    out("    trailing % also matches 0. Count the fields instead.)")
    now_ms = int(time.time() * 1000)
    n_cron_jobs = 0
    for r in con.execute(
            "select j.scheduler_id, "
            "json_extract(j.schedule_json,'$.kind') as kind, "
            "json_extract(j.schedule_json,'$.expression') as expression, "
            "j.state, j.next_run_at_ms, j.run_count, j.updated_at_ms, "
            "d.cron_id, d.name, d.target_session_id, "
            "d.session_target_mode, d.deleted_at_ms "
            "from local_runtime_v2_scheduler_jobs j "
            "left join local_runtime_v2_cron_definitions d "
            "on d.scheduler_id=j.scheduler_id "
            "order by j.state, j.scheduler_id"):
        if len(cron_fields(r["expression"])) != 5:
            continue
        n_cron_jobs += 1
        nxt = r["next_run_at_ms"]
        delta_min = (nxt - now_ms) / 60000.0 if nxt else None
        out(f"  cron={r['cron_id']} name={r['name']!r}")
        out(f"    expression={r['expression']!r} state={r['state']} "
            f"run_count={r['run_count']}")
        out(f"    next_run={local(nxt)}  "
            f"delta_from_now_min={None if delta_min is None else round(delta_min, 1)}")
        out(f"    target={r['target_session_id']} mode={r['session_target_mode']} "
            f"deleted={r['deleted_at_ms']}")
    out(f"  (cron-expression jobs listed = {n_cron_jobs}; "
        f"once-jobs are excluded by definition)")

    # D-4: the alarm, in the same breath as the census that used to hide it.
    report_cron_health(cron_health(con, now_ms), prefix="CRON-SCHEDULER")

    out("\n-- last 6 cron runs, ANY cron (is the scheduler alive today?) --")
    for r in con.execute(
            "select cron_id, trigger_source, status, session_id, created_at_ms, "
            "error_code, error from local_runtime_v2_cron_runs "
            "order by created_at_ms desc limit 6"):
        out(f"  {local(r['created_at_ms'])} cron={r['cron_id'][:8]} "
            f"src={r['trigger_source']} status={r['status']} "
            f"session={r['session_id']} err={r['error_code']}")
    return 0


def cmd_repair(args) -> int:
    con = open_rw()
    row = con.execute(
        "select * from local_runtime_queue_items where item_id=?",
        (args.item,)).fetchone()
    if row is None:
        out(f"  nothing to repair: {args.item} not present")
        return 0
    orig = dict(row)
    p = backup(f"repair-{args.item[:16]}", orig)
    out(f"[{now()}] BACKUP -> {p}")

    d = json.loads(row["data_json"])
    changed = []
    if "requestedTurnId" not in d:
        d["requestedTurnId"] = f"turn_{uuid.uuid4()}"
        changed.append("requestedTurnId")
    d.pop("deliveryAttempts", None)
    changed.append("-deliveryAttempts")
    d["source"] = "api"
    changed.append("source=api")
    new_fp = ROUTING_API
    if row["routing_fingerprint"] != new_fp:
        changed.append("routing_fingerprint")

    con.execute(
        "update local_runtime_queue_items set data_json=?, routing_fingerprint=?,"
        " source=?, dedupe_key=NULL where item_id=?",
        (json.dumps(d, separators=(",", ":")), new_fp, "api", args.item))
    con.commit()
    out(f"[{now()}] REPAIRED {args.item}  changed={changed}")

    chk = con.execute("select data_json, routing_fingerprint, source from "
                      "local_runtime_queue_items where item_id=?",
                      (args.item,)).fetchone()
    cd = json.loads(chk["data_json"])
    out(f"  verify: has requestedTurnId={'requestedTurnId' in cd} "
        f"has model={'model' in cd} fp_set={bool(chk['routing_fingerprint'])} "
        f"source={chk['source']}")
    ok = "requestedTurnId" in cd and bool(chk["routing_fingerprint"])
    out(f"  SHAPE_OK={ok}")
    return 0 if ok else 1


def split_pending(con: sqlite3.Connection, session: str, now_ms: int):
    """D-3.  Split a session's queued rows into LIVE, DEAD and CLAIMED.

    The shipped predicate was
        select count(*) ... where session_id=? and status='queued'
    -- it counted a row no matter how old, and nothing anywhere ever expired
    one (MEASURED: 0 rows in this store have ever carried expires_at_ms).
    One row for a session nobody is attached to therefore refused every future
    injection FOREVER.  The audit reproduced it deterministically:
    shipped 2,2,2,2,2 / cured 0,0,0,0,0.

    A row whose expires_at_ms has passed is not a pending message, it is a
    corpse, and counting it is precisely the wedge.  So the PREDICATE itself
    now honours the expiry the column already carries -- which is what makes
    the wedge impossible rather than merely unlikely.

    THREE buckets, not two, because a CLAIMED row is a third thing entirely:
    the runtime has taken it and is delivering it right now.  It is neither a
    pending message (refusing on it would refuse a wake that is already in
    flight) nor a corpse (we do not get to delete what the runtime owns).  An
    earlier version of this function had two buckets, and cmd_inject then
    deleted every expired row while cmd_prune kept every claimed row -- the two
    paths disagreed, and the inject path could have deleted a message the
    runtime was actively delivering.
    """
    rows = con.execute(
        "select item_id, created_at_ms, claim_id, expires_at_ms, "
        "routing_fingerprint, data_json from local_runtime_queue_items "
        "where session_id=? and status='queued' order by rowid",
        (session,)).fetchall()
    live, dead, claimed = [], [], []
    for r in rows:
        if r["claim_id"] is not None:
            claimed.append(r)
            continue
        exp = r["expires_at_ms"]
        (dead if (exp is not None and int(exp) <= now_ms) else live).append(r)
    return live, dead, claimed


def describe_row(r, now_ms: int) -> str:
    """D-3: a refusal must NAME what is blocking it, not just say 'refused'."""
    age = (now_ms - r["created_at_ms"]) / 60000.0
    bits = [f"item={r['item_id']}", f"age={age:.1f}min"]
    if r["claim_id"] is not None:
        bits.append(f"CLAIMED by {r['claim_id']}")
    if r["expires_at_ms"] is not None:
        bits.append(f"expires_at={local(r['expires_at_ms'])}"
                    f"({'EXPIRED' if int(r['expires_at_ms']) <= now_ms else 'live'})")
    else:
        bits.append("expires_at=NULL (nothing can ever reap it)")
    try:
        d = json.loads(r["data_json"] or "{}")
        bits.append(f"deliveryAttempts={len(d.get('deliveryAttempts') or [])}")
    except (ValueError, TypeError) as e:
        # Deliberately degraded: a row we cannot parse is still a row we must
        # report on, and refusing a wake because a diagnostic failed is the
        # wrong trade.  What is lost: the deliveryAttempts count for THIS row
        # only.  Loud, never silent.
        bits.append(f"deliveryAttempts=UNREADABLE({e!r})")
        print(f"  WARN: unparseable data_json for {r['item_id']}: {e!r}",
              file=sys.stderr, flush=True)
    return " ".join(bits)


def cmd_inject(args) -> int:
    con = open_rw()
    tpl = template_from(con, args.session, args.fallback_session)
    out(f"[{now()}] INJECT into session={args.session}")
    out(f"  template keys={sorted(tpl.keys())} (runtime-written row)")

    text = args.text
    if args.text_file:
        try:
            with open(args.text_file, "r", encoding="utf-8") as fh:
                text = fh.read().strip()
        except OSError as e:
            # LOUD: a missing prompt file must not silently degrade into a
            # generic message, and must not look like a successful wake.
            out(f"  ABORT: cannot read --text-file {args.text_file}: {e!r}")
            return 1
        out(f"  message read from {os.path.basename(args.text_file)} "
            f"({len(text)} chars)")

    now_ms = int(time.time() * 1000)
    live_rows, dead_rows, claimed_rows = split_pending(con, args.session, now_ms)
    for r in claimed_rows:
        # In flight: the runtime owns it.  Not pending (refusing on it would
        # refuse a message already being delivered) and not reapable.
        out(f"  IN-FLIGHT {r['item_id']} :: {describe_row(r, now_ms)} "
            f"(claimed by the runtime; not counted as pending)")
    if dead_rows:
        # An expired row must never be able to refuse a wake.  Drop it here,
        # with a backup, exactly like a stale one.  split_pending has already
        # excluded claimed rows, so this cannot touch what the runtime owns.
        for r in dead_rows:
            p = backup(f"expired-{r['item_id'][-8:]}", dict(r))
            con.execute("delete from local_runtime_queue_items where item_id=?",
                        (r["item_id"],))
            out(f"  DROPPED EXPIRED {r['item_id']} :: {describe_row(r, now_ms)} "
                f"backup={os.path.basename(p)}")
        con.commit()
        live_rows, _dead, _claimed = split_pending(con, args.session, now_ms)

    pending_rows = live_rows

    # --- prune stale rows -----------------------------------------------------
    # MEASURED WEDGE RISK: the dedupe refuses while ANY row is queued. A row the
    # running process never claims therefore blocks every future injection for
    # ever -- a permanent, silent dead channel. A row that has sat unclaimed past
    # --stale-mins is, by definition, not going to be delivered, so it is pruned
    # (with a backup) and the channel heals itself.
    stale_cut = now_ms - args.stale_mins * 60_000
    pruned = []
    for r in pending_rows:
        if r["claim_id"] is not None or r["created_at_ms"] >= stale_cut:
            continue
        p = backup(f"prune-{r['item_id'][-8:]}", dict(r))
        pruned.append((r["item_id"], local(r["created_at_ms"]), p))
    for item_id, _created, _p in pruned:
        con.execute("delete from local_runtime_queue_items where item_id=?",
                    (item_id,))
    if pruned:
        con.commit()
        for item_id, created, p in pruned:
            out(f"  PRUNED STALE {item_id} (queued {created}, never claimed) "
                f"backup={os.path.basename(p)}")
        pending_rows = [r for r in pending_rows
                        if r["item_id"] not in {i for i, _c, _p in pruned}]

    if pending_rows and not args.allow_stack:
        # D-3: name the blocker.  "REFUSED" alone was read as healthy for six
        # consecutive fires (12:07 -> 12:19, 12 minutes).
        out(f"  REFUSED: {len(pending_rows)} live row(s) already queued for this "
            f"session (pass --allow-stack to add anyway):")
        for r in pending_rows:
            out(f"    BLOCKING {describe_row(r, now_ms)}")
        return 2

    item_id = f"queue_{uuid.uuid4()}"
    stamp = datetime.now().strftime("%H:%M:%S")
    content = text or (
        f"[CRON {stamp}] Continua o trabalho real desta sessao: le o ultimo "
        f"receipt, faz o proximo passo mensuravel, e termina a linha "
        f"'Does your implementation meet the spec?'.")
    d = dict(tpl)
    d["itemId"] = item_id
    d["userMessageId"] = mint_user_message_id()          # D-1
    d["sessionId"] = args.session
    d["source"] = "api"
    d["status"] = "queued"
    d["createdAt"] = int(time.time() * 1000)
    d["clientRequestId"] = f"minimax-code_hb_{uuid.uuid4().hex[:16]}"
    d["requestedTurnId"] = f"turn_{uuid.uuid4()}"
    d["message"] = {"content": content, "attachments": []}
    d.pop("deliveryAttempts", None)

    # D-5, belt: set the expiry the column already carries.  The runtime's own
    # in-memory cron queue discards an undelivered entry after
    # OCe = 1800*1e3 = 30 min (chunk-U7ACBEGU.js), so 30 is the runtime's own
    # answer to "how long may a queued item wait".  This is NOT the whole cure
    # -- see cmd_prune -- because MEASURED: 0 rows in this store have ever
    # carried a non-null expires_at_ms, so the runtime honouring it is unproven.
    expires_at_ms = now_ms + args.row_ttl_mins * 60_000
    p = backup(f"inject-{args.session[-8:]}", d)
    out(f"  BACKUP -> {p}")

    con.execute(
        "insert into local_runtime_queue_items (session_id, item_id, status, "
        "created_at_ms, data_json, source, client_request_id, "
        "routing_fingerprint, expires_at_ms) values (?,?,?,?,?,?,?,?,?)",
        (args.session, item_id, "queued", d["createdAt"],
         json.dumps(d, separators=(",", ":")), "api", d["clientRequestId"],
         ROUTING_API, expires_at_ms))
    con.commit()
    out(f"  INSERTED item_id={item_id}")
    out(f"  userMessageId={d['userMessageId']} (len={len(d['userMessageId'])}, "
        f"runtime shape={USER_MESSAGE_ID_LENGTH})")
    out(f"  expires_at={local(expires_at_ms)} "
        f"(ttl={args.row_ttl_mins}min)")
    out(f"  content={content[:120]!r}")
    got = con.execute("select status, claim_id, routing_fingerprint, "
                      "expires_at_ms from local_runtime_queue_items "
                      "where item_id=?", (item_id,)).fetchone()
    out(f"  verify row: status={got['status']} claim={got['claim_id']} "
        f"fp_set={bool(got['routing_fingerprint'])} "
        f"expires_set={got['expires_at_ms'] is not None}")
    out("  NOTE: delivery is NOT proven by this insert.  It is proven ONLY by a "
        "turn whose local_runtime_turn_ingress.queue_item_ids_json names this "
        "item_id -- a role='user' text match is NOT proof (see receipt-24).")
    return 0


def cmd_arm_cron(args) -> int:
    con = open_rw()
    now_ms = int(time.time() * 1000)
    run_ms = now_ms + args.delay * 1000
    cron_id = f"probe-{uuid.uuid4().hex[:12]}"
    sched_id = f"sched-{uuid.uuid4().hex[:12]}"
    prompt = args.text or (
        "[CRON UNICO DE TESTE] Se esta mensagem chegou, o cron do runtime "
        "entrega mensagens a uma sessao viva como o dono digita. Responde "
        "em uma frase: quais sao os seus tres P0.")
    sched = {"kind": "cron", "expression": f"*/{args.every} * * * *",
             "timezone": "America/Sao_Paulo"}
    payload = {"cron_id": cron_id, "scheduler_id": sched_id, "prompt": prompt,
               "target_session_id": args.session, "schedule": sched,
               "first_run_local": local(run_ms), "now_local": local(now_ms)}
    p = backup(f"armcron-{cron_id}", payload)
    out(f"[{now()}] BACKUP -> {p}")

    con.execute(
        "insert into local_runtime_v2_cron_definitions (cron_id, scheduler_id,"
        " agent_name, name, prompt, target_session_id, revision, deleted_at_ms,"
        " created_at_ms, updated_at_ms, project, model, session_target_mode)"
        " values (?,?,?,?,?,?,0,NULL,?,?,?,?,?)",
        (cron_id, sched_id, "mavis", "probe single cron (wake test)", prompt,
         args.session, now_ms, now_ms, args.project,
         "minimax/MiniMax-M3.1-Flash-Preview", "sessionId"))
    con.execute(
        "insert into local_runtime_v2_scheduler_jobs (scheduler_id,"
        " handler_key, schedule_json, run_count, state, next_run_at_ms,"
        " created_at_ms, updated_at_ms, schedule_generation)"
        " values (?,'cron.run',?,0,'active',?,?,?,0)",
        (sched_id, json.dumps(sched, separators=(",", ":")), run_ms,
         now_ms, now_ms))
    con.commit()
    out(f"[{now()}] ARMED cron_id={cron_id}")
    out(f"  target_session={args.session} mode=sessionId")
    out(f"  schedule={sched['expression']}  first_run_local={local(run_ms)}"
        f"  (in {args.delay}s)")

    chk = con.execute(
        "select j.state, j.next_run_at_ms, j.schedule_json, d.target_session_id,"
        " d.session_target_mode from local_runtime_v2_scheduler_jobs j join"
        " local_runtime_v2_cron_definitions d on d.scheduler_id=j.scheduler_id"
        " where j.scheduler_id=?", (sched_id,)).fetchone()
    out(f"  verify: state={chk['state']} next_run={local(chk['next_run_at_ms'])} "
        f"target={chk['target_session_id']} mode={chk['session_target_mode']}")
    return 0


def cmd_prune(args) -> int:
    """Remove queued rows that have sat unclaimed past --stale-mins.

    WHY THIS EXISTS (measured 12:19): `mcode exec --session <id>` was refused
    with "An earlier queued message has priority" — twice. Two rows from 11:56
    and 12:06 were sitting in that session's queue and NOTHING was draining it,
    because an idle session has no process attached. So an old queued row is
    not a pending message: it is a permanent head-of-line block.
    """
    con = open_rw()
    now_ms = int(time.time() * 1000)
    if args.all_sessions:
        # D-5, THE PRIMARY CURE.  Why session-wide and not expiry alone:
        #   * the wedge is created by a PREDICATE keyed on session_id, so a
        #     session-scoped prune can never reach an orphan in a DIFFERENT
        #     session.  MEASURED orphan: queue_1dfd5c7c, session
        #     mvs_ea552229..., unclaimed, aged 959 -> 974 min over 5 samples,
        #     survived the one logged PRUNE event (POP = 1 event).
        #   * expires_at_ms is NOT a substitute: the column exists and is
        #     indexed, but MEASURED 0 rows in this store have ever carried it,
        #     so "the runtime reaps it" is unproven.  A cure you cannot
        #     demonstrate is not a cure.
        # Why it is SAFE session-wide, which is the obvious objection: the
        # per-row floor for a FOREIGN session is --orphan-min-mins (default
        # 60), not --stale-mins.  A live wake is minutes old by construction,
        # so 60 min can never reap one, and a CLAIMED row is never reaped at
        # any age.  60 min is also deliberately MORE conservative than the
        # runtime's own 30 min cron-queue TTL.
        rows = con.execute(
            "select * from local_runtime_queue_items where status='queued' "
            "order by rowid").fetchall()
        out(f"[{now()}] PRUNE --all-sessions target={args.session} "
            f"stale_mins={args.stale_mins} "
            f"orphan_min_mins={args.orphan_min_mins} "
            f"(POPULATION = whole queue table = {len(rows)} queued rows)")
    else:
        rows = con.execute(
            "select * from local_runtime_queue_items where session_id=? "
            "and status='queued' order by rowid", (args.session,)).fetchall()
        out(f"[{now()}] PRUNE session={args.session} "
            f"stale_mins={args.stale_mins} "
            f"(POPULATION = this session's queued rows = {len(rows)})")
    n = 0
    kept = 0
    for r in rows:
        age = (now_ms - r["created_at_ms"]) / 60000.0
        if args.all_sessions and r["session_id"] != args.session:
            floor = args.orphan_min_mins
        else:
            floor = args.stale_mins
        why_keep = None
        if r["claim_id"] is not None:
            why_keep = f"CLAIMED by {r['claim_id']}"
        elif r["expires_at_ms"] is not None and int(r["expires_at_ms"]) <= now_ms:
            why_keep = "EXPIRED (reaped as dead regardless of age)"
        elif age < floor:
            why_keep = f"younger than floor={floor}min"
        if why_keep:
            kept += 1
            out(f"  KEEP   {r['item_id'][-8:]} sess={r['session_id'][-8:]} "
                f"age={age:.1f}min floor={floor}min :: {why_keep}")
            continue
        p = backup(f"prune-{r['item_id'][-8:]}", dict(r))
        con.execute("delete from local_runtime_queue_items where item_id=?",
                    (r["item_id"],))
        n += 1
        out(f"  PRUNED {r['item_id'][-8:]} sess={r['session_id'][-8:]} "
            f"age={age:.1f}min floor={floor}min never claimed "
            f"backup={os.path.basename(p)}")
    con.commit()
    out(f"  pruned={n} kept={kept}")
    return 0


def cmd_cron_alarm(args) -> int:
    """D-2 + D-4, ONE alarm, driven by the driver on every fire.

    rc=3 when the runtime's own cron scheduler is stale while a cron is armed;
    rc=0 when it is healthy, or when no cron is armed (a store with nothing
    scheduled is not an outage).  Nothing here is inferred from a log line --
    it is read from the store every time, because the previous cron
    observability was a status line whose query matched nothing (D-2), which is
    how a 26.7 h outage read as "no crons configured".
    """
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    now_ms = int(time.time() * 1000)
    h = cron_health(con, now_ms)
    report_cron_health(h, prefix="CRON-ALARM")
    out(f"  POPULATION: cron_runs rows="
        f"{con.execute('select count(*) from local_runtime_v2_cron_runs').fetchone()[0]} "
        f"armed_active_crons={h['armed']} threshold={h['threshold_min']:.0f}min "
        f"(window = whole store)")
    if h["alarming"]:
        out(f"  ALARM: the runtime cron scheduler has produced no run in "
            f"{h['age_min']:.1f} min while {h['armed']} cron(s) are armed and "
            f"active. The owner is NOT being woken by the runtime's own cron.")
        return 3
    return 0


def cmd_wake_plan(args) -> int:
    """D-7.  Decide the transport, from signals that were MEASURED to predict.

    MEASURED (POP = 2 exec refusals, 13:05:05 and 13:08:59, both rc=4 with
    "Session already has an active Turn. Use queue send to deliver the message
    after it."):

      signal                                      predicts-busy?
      ------------------------------------------  --------------
      local_runtime_sessions.status               0 of 2  FALSE NEGATIVE
      an OPEN turn (accepted, not completed)      2 of 2  correct

    So `status` -- which the driver used to branch on -- is not merely
    imprecise, it was wrong on every refusal observed.  It read 'idle' at both.

    TWO signals, because no single one is safe:
      PRIMARY   a turn lease in local_runtime_session_locks, expires_at_ms > now.
                It is exactly what the runtime names in its own error, and it
                carries a real expiry: POP 10 rows store-wide, all owner_kind
                'turn', 0 without expiry, 0 already expired -- it cannot rot.
                CAVEAT, measured: locks are DELETED on turn completion, so the
                table is a good LIVE predicate and a useless HISTORICAL one.
      SECONDARY an open turn, BOUNDED by --max-open-turn-mins.  It has no
                expiry of its own and does linger: POP 10 unfinished rows, the
                oldest 60.3 min.  Unbounded, it would wedge the channel -- the
                same defect class as D-3.  Bound at 45 min because the turn
                duration distribution over POP 3743 completed turns is
                median 11.8 / p90 41.8 / p99 98.9 / max 253.6 min: past p90 a
                signal is cheaper to over-trust than to over-hold.

    And neither signal is trusted blindly: heartbeat.ps1 falls back to the
    QUEUE whenever exec is refused anyway.  A pre-flight read is a heuristic;
    the refusal is the fact.
    """
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    now_ms = int(time.time() * 1000)
    row = con.execute("select workspace_dir, status from local_runtime_sessions "
                      "where session_id=?", (args.session,)).fetchone()
    if row is None:
        out(f"NO-SUCH-SESSION {args.session}")
        return 1
    status = row["status"]

    lease = con.execute(
        "select owner_id, expires_at_ms from local_runtime_session_locks "
        "where session_id=? and owner_kind='turn'", (args.session,)).fetchone()
    lease_live = bool(lease and lease["expires_at_ms"]
                      and int(lease["expires_at_ms"]) > now_ms)

    opn = con.execute(
        "select turn_id, accepted_at_ms from local_runtime_turn_ingress "
        "where session_id=? and completed_at_ms is null "
        "order by accepted_at_ms desc limit 1", (args.session,)).fetchone()
    open_age = None if opn is None else (now_ms - opn["accepted_at_ms"]) / 60000.0
    open_fresh = open_age is not None and open_age <= args.max_open_turn_mins

    if lease_live:
        busy, reason = True, "turn-lease-held"
    elif open_fresh:
        busy, reason = True, f"open-turn-{open_age:.1f}min"
    else:
        busy = False
        reason = ("open-turn-too-old" if open_age is not None
                  else "no-lease-no-open-turn")

    # status is reported but NEVER decides.  It is printed so that a future
    # reader can see the disagreement instead of rediscovering it.
    out(f"SESSION-STATE session={args.session} status={status} "
        f"busy={'YES' if busy else 'NO'} reason={reason} "
        f"lease={'held' if lease_live else 'none'} "
        f"lease_expires={local(lease['expires_at_ms']) if lease_live else '-'} "
        f"open_turn={opn['turn_id'] if opn else '-'} "
        f"open_turn_age_min={'-' if open_age is None else f'{open_age:.1f}'} "
        f"max_open_turn_mins={args.max_open_turn_mins} "
        f"status_says_busy={'YES' if status != 'idle' else 'NO'} "
        f"(status DISAGREES={('YES' if ((status != 'idle') != busy) else 'NO')})")
    out(f"WORKSPACE {row['workspace_dir']}")
    return 0


def cmd_session_workspace(args) -> int:
    """Print the target session's own workspace_dir, and nothing else.

    MEASURED: `mcode exec --session <id>` fails with rc=4
      "Session workspace does not match --cwd" unless --cwd equals this value.
    Two sessions on this box differ (H:\\sotto vs C:\\Users\\Administrador),
    so hardcoding it is wrong by construction. Prints only the path, on the
    last line, so a caller can do `| Select-Object -Last 1`.
    """
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = con.execute(
        "select workspace_dir, status from local_runtime_sessions "
        "where session_id=?", (args.session,)).fetchone()
    if row is None:
        out(f"NO-SUCH-SESSION {args.session}")
        return 1
    out(f"SESSION {args.session} status={row[1]}")
    out(row[0])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["status", "repair", "inject", "arm-cron",
                                     "prune", "session-workspace", "cron-alarm",
                                     "wake-plan"])
    ap.add_argument("--session", default=os.environ.get(
        "SOTTO_SESSION", "mvs_a00662bff55242cb9b56c0f1165bdad7"))
    ap.add_argument("--item", default=BROKEN)
    ap.add_argument("--text", default=None)
    ap.add_argument("--text-file", default=None,
                    help="read the message from a file. Preferred over --text: "
                         "a multi-line argv is fragile on Windows, and the "
                         "orchestrator mandate is ~4 KB with newlines.")
    ap.add_argument("--project", default="H:\\sotto")
    ap.add_argument("--allow-stack", action="store_true")
    ap.add_argument("--fallback-session", default=None,
                    help="borrow the runtime-written template from this "
                         "session when the target has none of its own")
    ap.add_argument("--delay", type=int, default=60, help="first run in N seconds")
    ap.add_argument("--stale-mins", type=int, default=15,
                    help="a queued row older than this that was never claimed is "
                         "pruned instead of wedging the channel forever")
    ap.add_argument("--every", type=int, default=3, help="cron minutes")
    ap.add_argument("--all-sessions", action="store_true",
                    help="prune orphans in EVERY session, not just --session. "
                         "D-5: the wedge predicate is keyed on session_id, so a "
                         "session-scoped prune can never reach an orphan that "
                         "belongs to a session nobody is attached to.")
    ap.add_argument("--orphan-min-mins", type=int, default=60,
                    help="with --all-sessions, a FOREIGN session's row must be "
                         "older than this before it is reaped. Deliberately "
                         "larger than --stale-mins and larger than the runtime's "
                         "own 30 min cron-queue TTL, so a live wake is never "
                         "the thing that gets swept.")
    ap.add_argument("--row-ttl-mins", type=int, default=30,
                    help="expires_at_ms written on insert. 30 = the runtime's "
                         "own in-memory cron-queue TTL (OCe = 1800*1e3 in "
                         "chunk-U7ACBEGU.js). Belt to the sweep's braces: no row "
                         "in this store has ever carried it, so honouring it is "
                         "unproven.")
    ap.add_argument("--max-open-turn-mins", type=int, default=45,
                    help="D-7: an open turn older than this no longer marks the "
                         "session busy. 45 sits just above the measured p90 "
                         "turn duration (41.8 min over POP 3743 completed "
                         "turns); unbounded, this signal would wedge the "
                         "channel, which is the D-3 defect class.")
    args = ap.parse_args()
    return {"status": cmd_status, "repair": cmd_repair,
            "inject": cmd_inject, "arm-cron": cmd_arm_cron, "prune": cmd_prune,
            "session-workspace": cmd_session_workspace,
            "cron-alarm": cmd_cron_alarm,
            "wake-plan": cmd_wake_plan}[args.mode](args)


if __name__ == "__main__":
    sys.exit(main())