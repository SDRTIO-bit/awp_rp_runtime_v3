#!/usr/bin/env python3
"""快速真实 RP 试玩脚本 — 直接调用 persistent 节点跑 8+ 回合。

用法:
  python testing/quick_rp_playtest.py

环境要求:
  DEEPSEEK_API_KEY 已设置
  AWP_REAL_CARD_PATH 已设置（指向有效的角色卡 JSON）
"""

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# ── 项目根 ────────────────────────────────────────────────────────────────
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, str(Path(_PROJECT_ROOT).parent))

os.environ["AWP_RUNTIME_PROFILE"] = "test"
tmpdir = tempfile.mkdtemp(prefix="awp_playtest_")
os.environ["AWP_TEST_STORE_ROOT"] = tmpdir

CARD_PATH = os.environ.get("AWP_REAL_CARD_PATH", "<your-card-path>.json")
SESSION_ID = "playtest-001"
DIRECTOR_PROFILE = "deepseek-v4-pro-director"
WRITER_PROFILE = "deepseek-v4-flash-writer"
PRESET_PATH = "kedai_heavy_v1"

def safe(text, n=120):
    if not text:
        return "(empty)"
    return str(text).replace("\n", " ").strip()[:n]

def call_node(node_class, **inputs):
    func = getattr(node_class, "FUNCTION", "execute")
    return getattr(node_class(), func)(**inputs)

def extract(result, index):
    if isinstance(result, tuple) and index < len(result):
        return result[index]
    return {}

# ═══════════════════════════════════════════════════════════════════════
# 1. Bootstrap
# ═══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  1. BOOTSTRAP")
print("=" * 70)

from awp_rp_runtime_v3.nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap

boot = call_node(AWPV2PersistentBootstrap,
    source_path=CARD_PATH,
    session_id=SESSION_ID,
    greeting_id="g1",
    request_id=f"req_boot_{SESSION_ID}",
    run_id=f"run_{SESSION_ID}",
)
binding = extract(boot, 0)
opening = extract(boot, 1)
worldbook = extract(boot, 2)
diag = extract(boot, 4)
card_id = binding.get("logical_card_id", "?")[:20]
wb_count = len(worldbook.get("entries", []))
print(f"  card_id={card_id} wb_entries={wb_count} status={diag.get('outcome','?')}")

# ── 卡片摘要 ──
greetings = opening.get("available_greetings", [])
print(f"  greetings={len(greetings)}")

# ═══════════════════════════════════════════════════════════════════════
# 多回合循环
# ═══════════════════════════════════════════════════════════════════════
from awp_rp_runtime_v3.nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
from awp_rp_runtime_v3.nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn
from awp_rp_runtime_v3.nodes.continue_turn_execution_node import AWPV2ContinueTurn
from awp_rp_runtime_v3.nodes.accepted_text_output_node import AWPV2AcceptedTextOutput
from awp_rp_runtime_v3.nodes.turn_result_probe_node import AWPV2TurnResultProbe

# ── 玩家输入序列 ──
player_inputs = [
    # Turn 1 (first turn)
    "我轻轻推开院门，看见一个穿着粗布衣裳的年轻女子正在井边打水。",
    # Turn 2 (continuation)
    "那女子抬起头来，竟是周语晴。她看到我，眼圈一红，低声说：'你总算回来了。'",
    # Turn 3
    "我握住她的手，发现她手指冰凉。院里的老槐树下，晒着几件男子的衣物。",
    # Turn 4
    "屋里传来一声咳嗽，一个老妇人的声音响起：'语晴，是谁来了？'",
    # Turn 5
    "周语晴慌忙松开我的手，低声说：'是我婆婆。你……你先走吧。'",
    # Turn 6
    "我正要离开，门帘一挑，一个身形魁梧的汉子走了出来，正是村里的刘屠户。",
    # Turn 7
    "刘屠户上下打量着我，咧嘴一笑：'哟，这不是城里那位常来的公子吗？'",
    # Turn 8 (continuation, then Continue)
    "我没有理会刘屠户，径直看向周语晴。她的眼神里既有惊慌，又有一丝期盼。",
]

print(f"\n{'='*70}")
print(f"  2. FIRST TURN (Turn 1)")
print(f"{'='*70}")

# ── 第 1 回合 (first turn) ──
t1 = call_node(AWPV2PersistentFirstTurn,
    session_id=SESSION_ID,
    player_input=player_inputs[0],
    director_profile_id=DIRECTOR_PROFILE,
    writer_profile_id=WRITER_PROFILE,
    writer_preset_path=PRESET_PATH,
)
r1_receipt = extract(t1, 0)
r1_diag = extract(t1, 2)
r1_cs = extract(t1, 3)
r1_turn = extract(t1, 4)

print(f"  turn_id={r1_receipt.get('turn_id','?')[:20]}")
print(f"  turn_index={r1_receipt.get('turn_index','?')}")
print(f"  quality={r1_receipt.get('quality_verdict','?')}")
writer_text = r1_turn.get("writer_output", "")
print(f"  writer_len={len(writer_text)} {'<<< 1000字不及格' if len(writer_text) < 1000 else 'OK'}")
print(f"  preview: {safe(writer_text, 120)}")
print(f"  delegation={r1_diag.get('delegation_effects', {}).get('requested', [])}")
print(f"  memory_status={r1_diag.get('memory_curation_status','?')}")
print(f"  cs_revision={r1_cs.get('revision','?')}")

# ── 第 2-7 回合 (continuation turns) ──
for i in range(1, 7):
    print(f"\n{'='*70}")
    print(f"  3.{i} CONTINUATION (Turn {i+1})")
    print(f"{'='*70}")
    print(f"  player: {safe(player_inputs[i], 80)}")

    tc = call_node(AWPV2PersistentContinuationTurn,
        session_id=SESSION_ID,
        player_input=player_inputs[i],
        director_profile_id=DIRECTOR_PROFILE,
        writer_profile_id=WRITER_PROFILE,
        writer_preset_path=PRESET_PATH,
    )
    rc_receipt = extract(tc, 0)
    rc_diag = extract(tc, 2)
    rc_cs = extract(tc, 3)
    rc_turn = extract(tc, 4)
    rc_snap = extract(tc, 5)

    writer_text = rc_turn.get("writer_output", "")
    agent_triggers = rc_diag.get("delegation_effects", {}).get("requested", [])
    memory_status = rc_diag.get("memory_curation_status", "?")
    active_added = rc_diag.get("memory_effects", {}).get("active_added", 0)
    rag_added = rc_diag.get("memory_effects", {}).get("rag_added", 0)

    print(f"  turn_id={rc_receipt.get('turn_id','?')[:20]}")
    print(f"  turn_index={rc_receipt.get('turn_index','?')}")
    print(f"  quality={rc_receipt.get('quality_verdict','?')}")
    print(f"  writer_len={len(writer_text)} {'<<< 1000字不及格' if len(writer_text) < 1000 else 'OK'}")
    print(f"  preview: {safe(writer_text, 120)}")
    print(f"  agents_triggered={agent_triggers}")
    print(f"  memory={memory_status} active_added={active_added} rag_added={rag_added}")
    print(f"  cs_revision={rc_cs.get('revision','?')}")

    # Worldbook activation
    wb_ids = rc_diag.get("worldbook_entry_ids_activated", [])
    if wb_ids:
        print(f"  wb_activated={wb_ids[:5]}")

# ── 第 8 回合: Continue (world advance) ──
print(f"\n{'='*70}")
print(f"  4. CONTINUE (World Advance - Turn 8)")
print(f"{'='*70}")

t_cont = call_node(AWPV2ContinueTurn,
    session_id=SESSION_ID,
    director_profile_id=DIRECTOR_PROFILE,
    writer_profile_id=WRITER_PROFILE,
    writer_preset_path=PRESET_PATH,
)
cont_receipt = extract(t_cont, 0)
cont_diag = extract(t_cont, 2)
cont_cs = extract(t_cont, 3)
cont_turn = extract(t_cont, 4)

writer_text = cont_turn.get("writer_output", "")
agent_triggers = cont_diag.get("delegation_effects", {}).get("requested", [])
memory_status = cont_diag.get("memory_curation_status", "?")
active_added = cont_diag.get("memory_effects", {}).get("active_added", 0)

print(f"  turn_id={cont_receipt.get('turn_id','?')[:20]}")
print(f"  turn_index={cont_receipt.get('turn_index','?')}")
print(f"  quality={cont_receipt.get('quality_verdict','?')}")
print(f"  writer_len={len(writer_text)} {'<<< 1000字不及格' if len(writer_text) < 1000 else 'OK'}")
print(f"  preview: {safe(writer_text, 120)}")
print(f"  agents_triggered={agent_triggers}")
print(f"  memory={memory_status} active_added={active_added}")
print(f"  cs_revision={cont_cs.get('revision','?')}")

# ── Restart 验证 ──
print(f"\n{'='*70}")
print(f"  5. RESTART + CONTINUATION VERIFICATION")
print(f"{'='*70}")
from awp_rp_runtime_v3.runtime.runtime_store_factory import clear_registry_cache
clear_registry_cache()
print(f"  cache cleared, re-instantiating...")

t_restart = call_node(AWPV2PersistentContinuationTurn,
    session_id=SESSION_ID,
    player_input="我站在院子里，回想起刚才发生的一切，心里五味杂陈。",
    director_profile_id=DIRECTOR_PROFILE,
    writer_profile_id=WRITER_PROFILE,
    writer_preset_path=PRESET_PATH,
)
restart_diag = extract(t_restart, 2)
restart_cs = extract(t_restart, 3)
restart_turn = extract(t_restart, 4)
print(f"  outcome={restart_diag.get('outcome','?')}")
print(f"  cs_revision={restart_cs.get('revision','?')}")
print(f"  l1_count={len(restart_diag.get('l1_turn_ids_recalled',[]))}")
writer_text = restart_turn.get("writer_output", "")
print(f"  writer_len={len(writer_text)} {'<<< 1000字不及格' if len(writer_text) < 1000 else 'OK'}")
print(f"  preview: {safe(writer_text, 120)}")

# ── 摘要 ──
print(f"\n{'='*70}")
print(f"  PLAYTEST COMPLETE")
print(f"{'='*70}")
print(f"  Total turns: 8 (1 first + 6 continuation + 1 continue + 1 restart)")
print(f"  DB: {tmpdir}")

# 清理
clear_registry_cache()
import shutil
try:
    shutil.rmtree(tmpdir)
    print(f"  DB cleaned")
except:
    print(f"  DB kept at {tmpdir}")
