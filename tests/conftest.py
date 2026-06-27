"""Shared test fixtures."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from awp_rp_runtime_v2.testing.fakes import (
    FakeCardStateStore, FakeTurnRecordStore, FakeActiveMemoryStore,
    FakeRagMemoryStore, FakeTraceStore, FakeLLMProvider,
)
from awp_rp_runtime_v2.contracts.card_state import CardState, VariableEntry, SceneState


@pytest.fixture
def fake_card_state_store():
    return FakeCardStateStore()

@pytest.fixture
def fake_turn_record_store():
    return FakeTurnRecordStore()

@pytest.fixture
def fake_active_memory_store():
    return FakeActiveMemoryStore()

@pytest.fixture
def fake_rag_memory_store():
    return FakeRagMemoryStore()

@pytest.fixture
def fake_trace_store():
    return FakeTraceStore()

@pytest.fixture
def fake_llm():
    return FakeLLMProvider()
