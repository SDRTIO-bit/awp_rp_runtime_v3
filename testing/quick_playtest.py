#!/usr/bin/env python3
"""Quick RP playtest — bypasses ComfyUI, calls persistent nodes directly.

Usage:
  python testing/quick_playtest.py

Runs: bootstrap → first_turn → continuation → continue → restart_verify
Uses real DeepSeek models (requires DEEPSEEK_API_KEY).
"""

import sys, os, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ['AWP_RUNTIME_PROFILE'] = 'test'
_tmpdir = tempfile.mkdtemp(prefix='awp_play_')
os.environ['AWP_TEST_STORE_ROOT'] = _tmpdir

CARD_PATH = os.environ.get('AWP_REAL_CARD_PATH', '<your-card-path>.json')
SESSION_ID = 'playtest-' + os.urandom(4).hex()
DIRECTOR = 'deepseek-v4-flash-director'
WRITER = 'deepseek-v4-pro-writer'
PRESET = 'kedai_heavy_v1'

def safe(t, n=120): return str(t or '').replace('\n',' ').strip()[:n] or '(empty)'
def ext(r, i): return r[i] if isinstance(r, tuple) and i < len(r) else {}
def node(cls, **kw):
    fn = getattr(cls, 'FUNCTION', 'execute')
    return getattr(cls(), fn)(**kw)

def turn(num, kind, cls, player='', **kw):
    print(f'\n--- TURN {num} ({kind}) ---')
    if player: print(f'  IN: {safe(player, 80)}')
    kw.update(session_id=SESSION_ID, director_profile_id=DIRECTOR,
              writer_profile_id=WRITER, writer_preset_path=PRESET)
    if player: kw['player_input'] = player
    r = node(cls, **kw)
    d = ext(r, 2); cs = ext(r, 3); tr = ext(r, 4)
    wt = tr.get('writer_output','')
    wl = len(wt)
    flag = '<<<1000' if wl < 1000 else 'OK'
    print(f'  OUT: idx={ext(r,0).get("turn_index","?")} quality={ext(r,0).get("quality_verdict","?")} len={wl} {flag}')
    print(f'  TXT: {safe(wt, 120)}')
    agents = d.get('delegation_effects',{}).get('requested',[])
    mem = d.get('memory_curation_status','?')
    aa = d.get('memory_effects',{}).get('active_added',0)
    print(f'  AGENTS: {agents}  MEM: {mem} active={aa}  CS_REV: {cs.get("revision","?")}')
    return r

# ══ Run ══
from awp_rp_runtime_v2.nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap
from awp_rp_runtime_v2.nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
from awp_rp_runtime_v2.nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn
from awp_rp_runtime_v2.nodes.continue_turn_execution_node import AWPV2ContinueTurn
from awp_rp_runtime_v2.runtime.runtime_store_factory import clear_registry_cache

boot = node(AWPV2PersistentBootstrap, source_path=CARD_PATH, session_id=SESSION_ID,
            greeting_id='g1', request_id='req_'+SESSION_ID, run_id='run_'+SESSION_ID)
print(f'BOOT: wb={len(boot[2].get("entries",[]))}')

turn(1, 'first', AWPV2PersistentFirstTurn,
     '我轻轻推开院门，看见一个穿着粗布衣裳的年轻女子正在井边打水。')

turn(2, 'continuation', AWPV2PersistentContinuationTurn,
     '那女子抬起头来，竟是周语晴。她看到我，眼圈一红，低声说：你总算回来了。')

turn(3, 'continuation', AWPV2PersistentContinuationTurn,
     '我握住她的手，发现她手指冰凉。院里的老槐树下，晒着几件男子的衣物。')

turn(4, 'continuation', AWPV2PersistentContinuationTurn,
     '屋里传来一声咳嗽，一个老妇人的声音响起：语晴，是谁来了？')

turn(5, 'continuation', AWPV2PersistentContinuationTurn,
     '周语晴慌忙松开我的手，低声说：是我婆婆。你先走吧。')

turn(6, 'continuation', AWPV2PersistentContinuationTurn,
     '我正要离开，门帘一挑，一个身形魁梧的汉子走了出来，正是村里的刘屠户。')

turn(7, 'continuation', AWPV2PersistentContinuationTurn,
     '刘屠户上下打量着我，咧嘴一笑：哟，这不是城里那位常来的公子吗？')

turn(8, 'continue', AWPV2ContinueTurn)

# Restart verification
print('\n--- RESTART ---')
clear_registry_cache()
print('  cache cleared')
rr = node(AWPV2PersistentContinuationTurn, session_id=SESSION_ID,
          player_input='我站在院子里，回想刚才发生的一切。',
          director_profile_id=DIRECTOR, writer_profile_id=WRITER, writer_preset_path=PRESET)
rd = ext(rr, 2); rt = ext(rr, 4)
print(f'  outcome={rd.get("outcome","?")} l1={len(rd.get("l1_turn_ids_recalled",[]))}')
print(f'  len={len(rt.get("writer_output",""))} txt: {safe(rt.get("writer_output",""), 120)}')

# Cleanup
clear_registry_cache()
try: shutil.rmtree(_tmpdir)
except: pass
print('\nDONE')
