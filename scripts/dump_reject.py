import sqlite3, json, sys
db = r"F:\12\语英\awp_rp_runtime_v3\qingmei_out\empty_rooms\empty_rooms.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

print("=== chapter_drafts ===")
try:
    for r in con.execute("SELECT * FROM novel_chapter_draft ORDER BY chapter_index, revision"):
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 400:
                d[k] = v[:400] + "..."
        print(json.dumps(d, ensure_ascii=False, indent=2))
        print("---")
except Exception as e:
    print("err:", e)

print()
print("=== chapter_plans ===")
try:
    for r in con.execute("SELECT chapter_index, title, target_emotion, chapter_position FROM novel_chapter_plan ORDER BY chapter_index"):
        print(dict(r))
except Exception as e:
    print("err:", e)

print()
print("=== quality_decisions / issues (if any) ===")
for tbl in ("novel_quality_decision", "novel_quality_issue"):
    try:
        rows = list(con.execute(f"SELECT * FROM {tbl}"))
        print(f"{tbl}: {len(rows)} rows")
        for r in rows[:5]:
            print(dict(zip([c[0] for c in con.execute(f'SELECT * FROM {tbl} LIMIT 1').description], r)))
    except Exception as e:
        print(f"{tbl}: {e}")

print()
print("=== all novel tables ===")
for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'novel%' ORDER BY name"):
    print(r[0])
con.close()