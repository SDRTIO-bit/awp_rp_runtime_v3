"""Full pipeline test: NovelLedgerCurator with GLM-5.2"""
import os, sys, json, re
os.environ['NOVEL_LLM_PROVIDER'] = 'opencode'
os.environ['OPENCODE_API_KEY'] = 'sk-rqcMeOK7Hh9IMH5DTZ7jYXc3UEkHeYdRpJsHRitJ03G5IML7El4dhqpJSgEoLBSn'
os.environ['NOVEL_LLM_MODEL'] = 'glm-5.2'

# Bypass runtime/__init__.py issues by not importing the package directly
# Instead load each module via spec

import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# Load contracts
from contracts.novel_ledger import LedgerItem
from contracts.novel_chapter import ChapterPlan, ContentSummary

# Load the curator module
curator_mod = load_module("nlc", "runtime/novel_ledger_curator.py")
NovelLedgerCurator = curator_mod.NovelLedgerCurator

# Load the factory
factory_mod = load_module("nlf", "runtime/novel_llm_factory.py")
NovelLLMFactory = factory_mod.NovelLLMFactory
NovelLLMFactory._instance = None
NovelLLMFactory._adapters = {}

# Read chapter
chapter_text = open('novels/daily_high_school/output/chapter_01.md', encoding='utf-8').read()
chapter_text = re.sub(r'^# .+\n\n', '', chapter_text).strip()

# Build a minimal chapter plan
plan = ChapterPlan(
    chapter_id='test', project_id='daily-high-school', chapter_index=1,
    title='扣子错位的新学期', target_emotion='轻松→好奇', chapter_position='开幕章',
    content_summary=ContentSummary(cause='开学', development='陈默迟到+搬书+沈溪互动'),
)

class DummyStore:
    pass

class DummyRegistry:
    pass

registry = DummyRegistry()

# Create curator
curator = NovelLedgerCurator(registry)

# Call curate directly
print("Calling curate()...", flush=True)
result = curator.curate(
    chapter_text=chapter_text,
    chapter_plan=plan,
    current_ledger_items=[],
    previous_chapter_summaries=[],
)

print(f"\nResult type: {type(result)}")
print(f"Keys: {list(result.keys())}")
print(f"ledger_updates count: {len(result.get('ledger_updates', []))}")
updates = result.get('ledger_updates', [])
for i, item in enumerate(updates):
    print(f"  {i+1}. [{item.get('section','?')}] {item.get('entity','?')}: {item.get('content','')[:80]}")

# Also check what factory gave us
factory = NovelLLMFactory.get_instance()
print(f"\nFactory model: {factory.get_model('ledger_curator')}")
print(f"Factory max_tokens: {factory.get_max_tokens('ledger_curator')}")
