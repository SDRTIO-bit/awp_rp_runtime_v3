"""Test LedgerCurator standalone to diagnose LLM failure."""
import sys, traceback, json, sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT.parent))

from awp_rp_runtime_v3.runtime.novel_ledger_curator import NovelLedgerCurator
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_ledger import LedgerItem

print("=== Testing NovelLedgerCurator standalone ===")

# Load actual chapter 5 plan and text from DB
db = sqlite3.connect("novels/douluo_dalu/novel.db")

plan_row = db.execute(
    "SELECT plan_json FROM novel_chapter_plans WHERE chapter_index = 5"
).fetchone()
cols = db.execute("PRAGMA table_info('novel_chapter_drafts')").fetchall()
print("draft cols:", [r[1] for r in cols])

cols = db.execute("PRAGMA table_info('novel_chapter_plans')").fetchall()
print("plan cols:", [r[1] for r in cols])

draft_row = db.execute(
    "SELECT draft_json FROM novel_chapter_drafts ORDER BY created_at DESC LIMIT 1"
).fetchone()

if not plan_row or not draft_row:
    print("No ch5 data found!")
    sys.exit(1)

plan_data = json.loads(plan_row[0])
draft_data = json.loads(draft_row[0])

plan = ChapterPlan.from_dict(plan_data)
chapter_text = draft_data.get("text", "")[:3000]

print(f"Plan loaded: {plan.title}, {plan.target_chars} chars")
print(f"Text[:100]: {chapter_text[:100]}")

try:
    class FakeRegistry:
        pass

    curator = NovelLedgerCurator(FakeRegistry())
    print(f"Curator created OK, calling curate...")

    result = curator.curate(
        chapter_text=chapter_text,
        chapter_plan=plan,
        current_ledger_items=[],
    )
    print(f"SUCCESS! Result keys: {list(result.keys())}")
    for k, v in result.items():
        if isinstance(v, str):
            print(f"  {k}: {v[:200]}")
        elif isinstance(v, list):
            print(f"  {k}: {len(v)} items")
            for i, item in enumerate(v[:3]):
                if isinstance(item, dict):
                    print(f"    [{i}] {json.dumps(item, ensure_ascii=False)[:300]}")
                else:
                    print(f"    [{i}] {item}")
        else:
            print(f"  {k}: {v}")

except Exception as e:
    traceback.print_exc()
    print(f"\nFAILED: {e}")

db.close()
