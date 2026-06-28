"""Final 2×20 acceptance test with writer preset."""
import os, json, time, urllib.request, uuid, sqlite3

os.environ['AWP_REAL_LLM_E2E'] = '1'
os.environ['AWP_ALLOW_EXTERNAL_CARD_CONTENT'] = '1'
os.environ['AWP_RUNTIME_PROFILE'] = 'real'
os.environ['AWP_TEST_RUNTIME_NAMESPACE'] = f'final-20x2-{int(time.time())}'

CARD = r'C:\Users\zhao\Downloads\桃花村的公媳.json'
URL = 'http://127.0.0.1:8188'
DB = r'F:\12\语英\本体_ComfyUI\ComfyUI\awp_rp_runtime.db'
PRESET = 'kedai_heavy_v1'

DIRECTOR = 'deepseek-v4-pro-director'
WRITER = 'deepseek-v4-flash-writer'

def submit_and_wait(wf, timeout=600):
    cid = f'f20-{uuid.uuid4().hex[:6]}'
    p = json.dumps({'prompt': wf, 'client_id': cid}).encode()
    r = urllib.request.Request(f'{URL}/prompt', data=p, headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(r, timeout=30) as resp:
        pid = json.loads(resp.read())['prompt_id']
    dl = time.monotonic() + timeout
    while time.monotonic() < dl:
        r = urllib.request.Request(f'{URL}/history/{pid}')
        with urllib.request.urlopen(r, timeout=10) as resp:
            h = json.loads(resp.read())
            if pid in h:
                return pid, h[pid]
        time.sleep(3)
    raise TimeoutError(pid)

ts = int(time.time() * 1000)
sid_a = f'f20-A-{ts}'
sid_b = f'f20-B-{ts+1}'

TOTAL_TURNS = 20
results = {'A': [], 'B': []}
total_latency = 0
turn_count = 0

print(f'FINAL ACCEPTANCE: 2x{TOTAL_TURNS} with preset [{PRESET}]')
print(f'A: {sid_a}\nB: {sid_b}')

# Bootstrap
for label, sid in [('A', sid_a), ('B', sid_b)]:
    wf = {'1': {'class_type': 'AWPV2PersistentBootstrap', 'inputs': {
        'source_path': CARD, 'session_id': sid, 'greeting_id': 'g0',
        'request_id': f'bs-{sid}', 'run_id': f'run-bs-{sid}',
    }}}
    pid, e = submit_and_wait(wf, timeout=120)
    print(f'Bootstrap {label}: {e["status"]["status_str"]}')

# Checkpoint turns with scenario-specific inputs
checkpoints = {
    2:  {'A': '(压低声音)是一只青铜怀表。在明日辰时之前，万万不可让老丈知道。',
         'B': '(爽朗地)是一只银铃，做工可精致了。麻烦你现在就去告诉老丈，周货郎送来的。'},
    8:  {'A': '(试探)昨天我托你保管的东西，你没给别人看过吧？',
         'B': '(闲聊)上次给你的银铃，老丈看过了吧？他怎么说的？'},
    14: {'A': '(不经意地)对了，辰时快到了吧？我叮嘱过的时辰，没记错吧？',
         'B': '(不经意地)说起来，那银铃后来怎样了？我记得是让你马上告诉老丈的。'},
    19: {'A': '(最后确认)阿洛，怀表的事，你还记得我当初怎么跟你说的吗？',
         'B': '(最后确认)阿洛，我给你的银铃，你应该是一直带着的吧？老丈那边都知道了吧？'},
}

defaults = {
    'A': ['这里真安静。','你平时都做些什么？','村长身体还好吗？','我有点累了。','你说得对。',
          '这茶很香。','我以前也遇过类似的事。','那后来呢？','你觉得这样做好吗？','我明白了。',
          '嗯，记住了。','我们再走走？','这里我来过的。','天快黑了。','那就好。'],
    'B': ['这地方真不错。','收成怎么样？','老丈最近忙吗？','我有点饿了。','有道理。',
          '这花香得很。','我听过差不多的故事。','然后呢？','你拿主意吧。','有道理。',
          '好的。','再去那边看看？','这路我认得。','太阳下山了。','就这么定了。'],
}

for turn_num in range(1, TOTAL_TURNS + 1):
    for label, sid in [('A', sid_a), ('B', sid_b)]:
        tid = f't{turn_num}-{sid}'

        if turn_num in checkpoints and label in checkpoints[turn_num]:
            pinput = checkpoints[turn_num][label]
        else:
            dl = defaults[label]
            pinput = dl[(turn_num - 1) % len(dl)]

        start = time.monotonic()

        base_inputs = {
            'session_id': sid, 'player_input': pinput,
            'turn_id': tid, 'request_id': f'req-{tid}',
            'workflow_run_id': f'wfr-{tid}', 'trace_id': f'trc-{tid}',
            'director_profile_id': DIRECTOR, 'writer_profile_id': WRITER,
            'writer_preset_path': PRESET,
        }

        if turn_num == 1:
            wf = {'1': {'class_type': 'AWPV2PersistentFirstTurn', 'inputs': base_inputs}}
        else:
            wf = {'1': {'class_type': 'AWPV2PersistentContinuationTurn', 'inputs': base_inputs}}

        pid, e = submit_and_wait(wf, timeout=600)
        took = int(time.monotonic() - start)
        total_latency += took
        turn_count += 1
        s = e['status']['status_str']

        conn = sqlite3.connect(DB)
        rows = conn.execute('SELECT record_json FROM turn_records WHERE turn_id=?', (tid,)).fetchall()
        wlen = 0
        if rows:
            rec = json.loads(rows[0][0])
            wlen = len(rec.get('writer_output', ''))
        conn.close()

        results[label].append({'turn': turn_num, 'status': s, 'time': took, 'text_len': wlen})
        mem = '!!!' if wlen >= 1200 else ('**' if wlen >= 800 else '')
        print(f'  {label}T{turn_num:02d}: {s} {took:3d}s {wlen:5d}chars {mem}')

# Verification
conn = sqlite3.connect(DB)
print(f'\n=== FINAL ===')
for label, sid in [('A', sid_a), ('B', sid_b)]:
    turns = conn.execute('SELECT COUNT(*) FROM turn_records WHERE session_id=?', (sid,)).fetchone()[0]
    cs = conn.execute('SELECT revision FROM card_states WHERE session_id=?', (sid,)).fetchone()
    mem = conn.execute('SELECT COUNT(*) FROM active_memory_records WHERE session_id=?', (sid,)).fetchone()[0]
    rag = conn.execute('SELECT COUNT(*) FROM rag_memory_records WHERE session_id=?', (sid,)).fetchone()[0]
    trace = conn.execute('SELECT COUNT(*) FROM execution_traces WHERE session_id=?', (sid,)).fetchone()[0]
    print(f'{label}: {turns}T rev={cs[0]} L2={mem} L3={rag} traces={trace}')

a_tr = {r[0] for r in conn.execute('SELECT turn_id FROM turn_records WHERE session_id=?', (sid_a,))}
b_tr = {r[0] for r in conn.execute('SELECT turn_id FROM turn_records WHERE session_id=?', (sid_b,))}
a_mem = {r[0] for r in conn.execute('SELECT memory_id FROM active_memory_records WHERE session_id=?', (sid_a,))}
b_mem = {r[0] for r in conn.execute('SELECT memory_id FROM active_memory_records WHERE session_id=?', (sid_b,))}
print(f'Isolation: TR_overlap={len(a_tr & b_tr)} Mem_overlap={len(a_mem & b_mem)}')

conn.close()

failed = sum(1 for r in results['A'] + results['B'] if r['status'] != 'success')
avg = total_latency / turn_count if turn_count else 0
p1200 = sum(1 for r in results['A'] + results['B'] if r['text_len'] >= 1200)
n = TOTAL_TURNS * 2
print(f'\n{n}/{n} turned, {failed} failed, avg {avg:.0f}s/turn')
print(f'Preset >=1200chars: {p1200}/{n}')
