#!/usr/bin/env python3
"""20 回合长对话测试 — 验证记忆系统、子Agent触发、工具注册、叙事质量。

用法:
  python testing/twenty_turn_test.py

输出: 每回合评分 + 最终报告
"""

import sys, os, tempfile, shutil, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ['AWP_RUNTIME_PROFILE'] = 'test'
_tmpdir = tempfile.mkdtemp(prefix='awp_20t_')
os.environ['AWP_TEST_STORE_ROOT'] = _tmpdir

CARD_PATH = r'C:\Users\zhao\Downloads\桃花村的公媳.json'
SESSION_ID = '20turn-' + os.urandom(4).hex()
DIRECTOR = 'deepseek-v4-flash-director'
WRITER = 'deepseek-v4-pro-writer'
PRESET = 'kedai_heavy_v1'

def safe(t, n=120): return str(t or '').replace('\n',' ').strip()[:n] or '(empty)'
def ext(r, i): return r[i] if isinstance(r, tuple) and i < len(r) else {}
def node(cls, **kw):
    fn = getattr(cls, 'FUNCTION', 'execute')
    return getattr(cls(), fn)(**kw)

from awp_rp_runtime_v2.nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap
from awp_rp_runtime_v2.nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
from awp_rp_runtime_v2.nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn
from awp_rp_runtime_v2.nodes.continue_turn_execution_node import AWPV2ContinueTurn

# ═══ 20 回合玩家输入（推进剧情） ═══
player_inputs = [
    # Turn 1 (first turn)
    "我推开院门，看见一个穿粗布衣裳的年轻女子在井边打水。",
    # Turn 2
    "那女子抬起头，竟是周语晴。她眼圈一红：'你总算回来了。'",
    # Turn 3
    "我握住她的手，她手指冰凉。院里晒着几件男子的衣物。",
    # Turn 4
    "屋里传来咳嗽声，一个老妇人问：'语晴，是谁来了？'",
    # Turn 5
    "周语晴低声说：'是我婆婆。你……先走吧。'",
    # Turn 6
    "门帘一挑，刘屠户走了出来，打量着我：'哟，城里来的公子？'",
    # Turn 7
    "我没有理他，问语晴：'你过得好吗？'她低头不语。",
    # Turn 8
    "婆婆走了出来，看了我一眼，对语晴说：'还不快去做饭。'",
    # Turn 9
    "我跟进厨房，语晴切着菜，眼泪掉在案板上。",
    # Turn 10
    "她终于开口：'当初你走了以后，是刘屠户帮我爹还的债。'",
    # Turn 11
    "'所以你就嫁给他了？'我问。她点了点头，不敢看我。",
    # Turn 12
    "外面传来刘屠户的声音：'周语晴，给我倒酒！'她慌忙擦泪。",
    # Turn 13
    "我拦住她：'别去。'她摇头：'你不懂，这是我的命。'",
    # Turn 14
    "刘屠户掀帘进来，看见我们站在一起，脸色一沉。",
    # Turn 15
    "'好你个周语晴，趁老子不在偷汉子？'他抬手就要打。",
    # Turn 16
    "我挡在语晴前面，刘屠户的拳头停在我鼻尖前。",
    # Turn 17
    "婆婆听到动静赶来，拉住刘屠户：'使不得！这是咱家亲戚！'",
    # Turn 18
    "刘屠户冷笑：'亲戚？我看是姘头吧！'语晴脸色煞白。",
    # Turn 19
    "我拉起语晴的手：'跟我走。'她犹豫着，回头看了一眼这个家。",
    # Turn 20
    "最终她松开我的手，退后一步：'你走吧，这是我的命。'",
]

# ═══ Bootstrap ═══
boot = node(AWPV2PersistentBootstrap, source_path=CARD_PATH, session_id=SESSION_ID,
            greeting_id='g1', request_id='req_'+SESSION_ID, run_id='run_'+SESSION_ID)
wb_entries = len(boot[2].get('entries',[]))
print(f'BOOT: wb={wb_entries}')
print()

# ═══ 存储每回合结果 ═══
results = []

for i, inp in enumerate(player_inputs):
    turn_num = i + 1
    kind = 'first' if i == 0 else 'continuation'
    if i == 19:
        kind = 'continue'  # Turn 20 用 Continue 表达世界推进

    cls = AWPV2PersistentFirstTurn if i == 0 else (
        AWPV2ContinueTurn if i == 19 else AWPV2PersistentContinuationTurn
    )

    r = node(cls, session_id=SESSION_ID, player_input=inp,
             director_profile_id=DIRECTOR, writer_profile_id=WRITER,
             writer_preset_path=PRESET)

    d = ext(r, 2); cs = ext(r, 3); tr = ext(r, 4)
    wt = tr.get('writer_output','') if tr else ''
    wl = len(wt)
    agents = d.get('delegation_effects',{}).get('requested',[]) if d else []
    mem_status = d.get('memory_curation_status','?') if d else '?'
    aa = d.get('memory_effects',{}).get('active_added',0) if d else 0
    ra = d.get('memory_effects',{}).get('rag_added',0) if d else 0
    cs_rev = cs.get('revision','?') if cs else '?'
    wb_ids = d.get('worldbook_entry_ids_activated',[]) if d else []
    qv = d.get('quality_verdict','?') if d else '?'
    steps = d.get('steps_completed',[]) if d else []

    results.append({
        'turn': turn_num, 'kind': kind,
        'player': inp, 'writer': wt,
        'len': wl, 'quality': qv,
        'agents': agents, 'mem_status': mem_status,
        'active_added': aa, 'rag_added': ra,
        'cs_rev': cs_rev, 'wb_ids': wb_ids,
        'steps': steps,
    })

    flag = '<<<1000' if wl < 1000 else 'OK'
    print(f'T{turn_num:2d} ({kind:12s}) len={wl:4d} {flag:8s} q={qv:8s} agents={str(agents):40s} mem={mem_status:8s} active={aa} rag={ra} cs={cs_rev}')

# ═══ 质量评分 ═══
print('\n' + '='*80)
print('  每回合质量评分')
print('='*80)

scores = []
for r in results:
    score = 0
    reasons = []

    # 字数 (0-40分)
    if r['len'] >= 1200:
        score += 40
    elif r['len'] >= 1000:
        score += 30
        reasons.append('字数接近达标')
    elif r['len'] >= 500:
        score += 15
        reasons.append('字数不足')
    else:
        reasons.append('字数严重不足')

    # Quality verdict (0-20分)
    if r['quality'] == 'accept':
        score += 20
    elif r['quality'] == 'revise':
        score += 5
        reasons.append('质量门REVISE')
    else:
        reasons.append('质量门REJECT')

    # 子Agent触发 (0-15分)
    if len(r['agents']) >= 2:
        score += 15
    elif len(r['agents']) >= 1:
        score += 10
        reasons.append('子Agent较少')
    else:
        reasons.append('无子Agent触发')

    # 记忆系统 (0-15分)
    if r['active_added'] > 0 or r['rag_added'] > 0:
        score += 15
    else:
        reasons.append('记忆未写入')

    # 状态变化 (0-10分)
    if i > 0 and results[i-1]['cs_rev'] != r['cs_rev']:
        score += 10
    else:
        reasons.append('状态未变化')

    scores.append({'turn': r['turn'], 'score': score, 'reasons': reasons, 'len': r['len']})

# 输出评分
total = 0
for s in scores:
    total += s['score']
    tag = 'PASS' if s['score'] >= 60 else 'FAIL'
    print(f'  T{s["turn"]:2d}: {s["score"]:3d}/100 {tag:5s} len={s["len"]:4d} reasons={s["reasons"]}')

avg = total / len(scores)
print(f'\n  平均分: {avg:.1f}/100')

# ═══ 最终报告 ═══
print('\n' + '='*80)
print('  最终报告')
print('='*80)

# 1. 各子Agent触发统计
agent_counts = {}
for r in results:
    for a in r['agents']:
        agent_counts[a] = agent_counts.get(a, 0) + 1
print(f'\n  子Agent触发统计:')
for a, c in sorted(agent_counts.items()):
    print(f'    {a:30s}: {c}/20 回合')
untriggered = [a for a in ['d1_history_recall','d2_opportunity','d3_world_life','d4_emotion_rel','d5_continuity'] if a not in agent_counts]
if untriggered:
    print(f'  未触发: {untriggered}')

# 2. 记忆系统统计
mem_active_total = sum(r['active_added'] for r in results)
mem_rag_total = sum(r['rag_added'] for r in results)
mem_active_turns = sum(1 for r in results if r['active_added'] > 0)
mem_rag_turns = sum(1 for r in results if r['rag_added'] > 0)
print(f'\n  记忆系统:')
print(f'    ActiveMemory: {mem_active_total} 条, 分布在 {mem_active_turns}/20 回合')
print(f'    RAG Memory: {mem_rag_total} 条, 分布在 {mem_rag_turns}/20 回合')

# 3. 字数统计
long_enough = sum(1 for r in results if r['len'] >= 1000)
short = sum(1 for r in results if r['len'] < 500)
print(f'\n  字数:')
print(f'    >=1000字: {long_enough}/20 回合')
print(f'    <500字: {short}/20 回合')

# 4. 状态变化
revs = set()
for r in results:
    if r['cs_rev'] != '?':
        revs.add(r['cs_rev'])
print(f'\n  CardState 修订数: {len(revs)} 个不同版本')

# 5. 工具调用
print(f'\n  工具调用: 生产中未注册 runner，工具系统未激活')
print(f'    D1-D5 各注册了 allowed_tools 但 register_runner 在生产中从未调用')
print(f'    当前子Agent LLM 走的是 sub_agent_llm_runner.py 直接调 DeepSeek Flash')

# 6. 结论
print(f'\n  结论:')
if avg >= 70:
    print(f'    ✅ 平均分 {avg:.1f}/100 — RP 体验良好，可以投入真实使用')
elif avg >= 50:
    print(f'    ⚠️ 平均分 {avg:.1f}/100 — 基本可用，但有改进空间')
else:
    print(f'    ❌ 平均分 {avg:.1f}/100 — 需要修复核心问题')

# 清理
from awp_rp_runtime_v2.runtime.runtime_store_factory import clear_registry_cache
clear_registry_cache()
try: shutil.rmtree(_tmpdir)
except: pass
print(f'\n  数据库已清理')
