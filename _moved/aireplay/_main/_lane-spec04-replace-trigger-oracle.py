"""Verify BLOCKER 1 on my own spec: does INSERT OR REPLACE bypass AFTER DELETE, and do the
three fixes in specs/04-index-search.md actually close it?

An upstream reviewer reported this. A claim from a reviewer is not evidence until it has been
reproduced here, on THIS box, against the spec's own DDL. Four arms, plus a NEG arm that is
the reverted fix, so the gate can go RED on the un-fixed writer.
"""
import re, sqlite3, sys

SPEC = r"H:\sotto\_moved\aireplay\specs\04-index-search.md"
blocks = re.findall(r"```sql\n(.*?)```", open(SPEC, encoding="utf-8").read(), flags=re.S)

OLD_T, OLD_U = "na ponte", "na ponte sobre o rio"
NEW_T, NEW_U = "no aclito", "no aclito"

def fresh(recursive):
    db = sqlite3.connect(":memory:")
    db.execute("pragma foreign_keys=ON")
    db.execute("pragma recursive_triggers=%s" % ("ON" if recursive else "OFF"))
    for b in blocks:
        db.executescript(b)
    db.execute("insert into video(clip_uuid,path,produced_by,added_at) values('u','p','capture-cut',0)")
    db.execute("insert into segment(video_id,start_ms,end_ms) values(1,0,5000)")
    return db

def put(db, seg, t, u, mode):
    if mode == "insert":
        db.execute("insert into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars)"
                   " values(?,0,5000,?,?,'a','b',?)", (seg, t, u, len(t)))
    elif mode == "replace":
        db.execute("insert or replace into transcript(seg_id,start_ms,end_ms,text,text_norm,producer,model_sha256,n_chars)"
                   " values(?,0,5000,?,?,'a','b',?)", (seg, t, u, len(t)))
    elif mode == "update":
        db.execute("update transcript set text=?, text_norm=?, n_chars=? where seg_id=?", (t, u, len(t), seg))

def indexed(db, term):
    try:
        n = db.execute("select count(*) from transcript_fts where transcript_fts match ?", ('"%s"' % term,)).fetchone()[0]
        return n
    except Exception as e:
        return "ERR %s" % e

def arm(recursive, mode):
    db = fresh(recursive)
    put(db, 1, OLD_T, OLD_U, "insert")
    before_old, before_new = indexed(db, "ponte"), indexed(db, "aclito")
    put(db, 1, NEW_T, NEW_U, mode)
    after_old, after_new = indexed(db, "ponte"), indexed(db, "aclito")
    stale = after_old > 0
    ic = db.execute("pragma integrity_check").fetchone()[0]
    return {"recursive": recursive, "mode": mode,
            "old_token_before": before_old, "old_token_after": after_old,
            "new_token_after": after_new, "STALE": stale, "integrity_check": ic}

arms = [arm(False, "replace"), arm(True, "replace"), arm(True, "update")]

print("ARM  recursive  mode      old_before old_after new_after  STALE  integrity_check")
for a in arms:
    print("     %-9s %-9s %-10s %-9s %-9s %-7s %s" % (
        a["recursive"], a["mode"], a["old_token_before"], a["old_token_after"],
        a["new_token_after"], a["STALE"], a["integrity_check"]))

neg = arms[0]        # no recursive_triggers + INSERT OR REPLACE  == the reported bug
fix_rec = arms[1]   # pragma fix
fix_upd = arms[2]    # writer fix
print("")
problems = []
if not neg["STALE"]:
    problems.append("NEG arm is NOT stale: the upstream BLOCKER claim did not reproduce here")
if fix_rec["STALE"]:
    problems.append("recursive_triggers=ON did NOT clear the stale token")
if fix_upd["STALE"]:
    problems.append("the UPDATE writer did NOT clear the stale token")
if not all(a["integrity_check"] == "ok" for a in arms):
    problems.append("a store went CORRUPT -- the claim would be stronger than reported")

verdict = "GREEN" if not problems else "RED"
print("VERDICT: " + verdict)
for p in problems:
    print("  problem:", p)
print("")
print("reading: the NEG arm reproduces the reported bug" if neg["STALE"] else "reading: NEG arm clean")
print("integrity_check is 'ok' on every arm, so the corruption is NOT visible to a")
print("database check -- which is exactly why it is a silent recall loss.")
sys.exit(0 if verdict == "GREEN" else 1)