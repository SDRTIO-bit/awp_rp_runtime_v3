"""Test GLM curator with temperature=1.0 (adapter default)."""
import os, json, re
os.environ['OPENCODE_API_KEY'] = 'sk-rqcMeOK7Hh9IMH5DTZ7jYXc3UEkHeYdRpJsHRitJ03G5IML7El4dhqpJSgEoLBSn'
from openai import OpenAI

chapter_text = open('novels/daily_high_school/output/chapter_01.md', encoding='utf-8').read()
chapter_text = re.sub(r'^# .+\n\n', '', chapter_text).strip()

system = open('runtime/novel_ledger_curator.py', encoding='utf-8').read()
system = system.split('LEDGER_CURATOR_PROMPT = """')[1].split('"""')[0].strip()

c = OpenAI(api_key=os.environ['OPENCODE_API_KEY'], base_url='https://opencode.ai/zen/go/v1', timeout=180)

# Reproduce full pipeline prompt
parts = []
parts.append("=== CURRENT LEDGER (existing facts) ===\n"
    "- [active] [open_threads] 苏念: 三年前的遗憾未解决\n"
    "- [active] [character_state] 赵小麦: 体委，未登场\n")
parts.append(f"=== CHAPTER PLAN ===\n{{'chapter_id': 'ch1', 'title': '扣子错位的新学期', 'chapter_index': 1}}")
parts.append(f"\n=== CHAPTER TEXT ===\n{chapter_text[:6000]}")
parts.append("\n=== OUTPUT (strict JSON, no markdown wrapping) ===\n"
    '{"chapter_summary": "", "ledger_updates": [], "ledger_resolves": [], "foreshadowing_changes": []}')
user = "\n".join(parts)

for temp in [0.3, 0.7, 1.0]:
    results = []
    print(f"\n=== temperature={temp} (3 runs) ===")
    for run in range(3):
        r = c.chat.completions.create(model='glm-5.2', messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ], max_tokens=4000, temperature=temp)
        raw = r.choices[0].message.content
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            data = json.loads(text)
            n = len(data.get('ledger_updates', []))
            results.append(n)
            print(f"  run{run+1}: {n} items, completion={r.usage.completion_tokens}")
        except json.JSONDecodeError:
            results.append(-1)
            print(f"  run{run+1}: JSON ERROR, completion={r.usage.completion_tokens}")
    print(f"  summary: min={min(results)}, max={max(results)}, avg={sum(results)/3:.1f}")
