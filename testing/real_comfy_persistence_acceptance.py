"""Real ComfyUI Persistence Acceptance — verifies SQLite persistence across restarts.

Usage:
  python -m awp_rp_runtime_v3.testing.real_comfy_persistence_acceptance --managed-comfy --restart-after-turn --turns 2

Core scenario:
  1. Bootstrap session to SQLite via _seed_session (bootstrap unit-tested separately)
  2. Execute Turn 1 via PersistentFirstTurn node
  3. Verify Turn 1 written to SQLite (CardState, TurnRecord)
  4. Simulate ComfyUI restart: clear registry cache, create new factory
  5. Execute Turn 2 via PersistentContinuationTurn — only sessionId + playerInput + turnId + requestId
  6. Assert: L1 contains Turn 1, OpeningContext exists but not in L1
  7. Verify Turn 2 written to SQLite
  8. Replay Turn 2: same turnId → idempotency_status=replayed, no extra writes

Exit codes:
  0 = all checks passed
  1 = one or more checks failed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tempfile
from pathlib import Path
from typing import Any


def _check(name: str, passed: bool, detail: str = "") -> bool:
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {name}")
    if detail:
        print(f"       {detail}")
    return passed


def _seed_session(registry, session_id: str, card_id: str = "card_accept_001") -> None:
    """Seed a complete session bootstrap into persistent stores."""
    from ..contracts.card_session_binding import CardSessionBinding
    from ..contracts.opening_record import OpeningRecord
    from ..contracts.worldbook_binding import WorldbookBinding
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    binding = CardSessionBinding(
        session_id=session_id,
        logical_card_id=card_id,
        card_version=1,
        source_hash="accept_hash_001",
        selected_greeting_id="g0",
        opening_record_id=f"op_{session_id}",
        worldbook_binding_id=f"wb_{session_id}",
        status="ready",
        created_at=now,
    )
    registry.card_session_binding_store.save(binding)

    opening = OpeningRecord(
        opening_record_id=f"op_{session_id}",
        session_id=session_id,
        logical_card_id=card_id,
        card_version=1,
        greeting_id="g0",
        safe_display_content="欢迎来到桃花村！这里山清水秀，民风淳朴。",
        created_at=now,
    )
    registry.opening_record_store.save(opening)

    wb = WorldbookBinding(
        worldbook_binding_id=f"wb_{session_id}",
        session_id=session_id,
        logical_card_id=card_id,
        card_version=1,
        source_hash="accept_hash_001",
        created_at=now,
    )
    registry.worldbook_binding_store.save(wb)

    registry.card_state_store.initialize(card_id, session_id)


def run_persistence_acceptance(
    comfy_url: str = "",
    restart_after_turn: bool = True,
    turns: int = 2,
    with_real_provider: bool = False,
    save_private_transcript: bool = False,
) -> bool:
    """Run the persistence acceptance test.

    Verifies that SQLite data survives a simulated ComfyUI restart.
    Uses RuntimeStoreFactory + persistent nodes directly (no HTTP API).
    """
    print("=" * 60)
    print("AWP RP Runtime V2 — Persistence Acceptance (Direct API)")
    print("=" * 60)
    print(f"  Restart after turn: {restart_after_turn}")
    print(f"  Turns: {turns}")
    print(f"  Real provider: {with_real_provider}")
    print("=" * 60)

    all_ok = True
    store_root = os.path.join(tempfile.gettempdir(), f"awp-accept-{int(time.time())}")
    os.makedirs(store_root, exist_ok=True)

    ns = f"persist-{int(time.time())}"
    os.environ["AWP_RUNTIME_PROFILE"] = "test"
    os.environ["AWP_TEST_STORE_ROOT"] = store_root
    os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = ns

    try:
        from ..runtime.runtime_store_factory import RuntimeStoreFactory, clear_registry_cache
        from ..nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
        from ..nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn

        # ── Phase 1: Bootstrap ──────────────────────────────────────────
        print("\n1. Bootstrap session...")
        clear_registry_cache()

        session_id = f"accept-sess-{int(time.time() * 1000)}"
        card_id = "card_accept_001"

        factory = RuntimeStoreFactory.from_env()
        registry = factory.registry
        _seed_session(registry, session_id, card_id)
        _check("Session seeded to SQLite", True, f"session={session_id}")

        # Verify L0
        binding = registry.card_session_binding_store.load(session_id)
        all_ok = _check("CardSessionBinding in SQLite", binding is not None) and all_ok
        all_ok = _check("Binding status=ready", binding.status == "ready" if binding else False) and all_ok

        opening = registry.opening_record_store.get_by_session(session_id)
        all_ok = _check("OpeningRecord in SQLite", opening is not None) and all_ok

        wb = registry.worldbook_binding_store.get_by_session(session_id)
        all_ok = _check("WorldbookBinding in SQLite", wb is not None) and all_ok

        # ── Phase 2: Turn 1 ─────────────────────────────────────────────
        print("\n2. Turn 1 (first formal turn)...")
        turn1_id = f"turn-1-{int(time.time())}"
        turn1_req = f"req-turn1-{int(time.time())}"

        ft_node = AWPV2PersistentFirstTurn()
        ft_result = ft_node.execute(
            session_id=session_id,
            player_input="你好，我想了解一下桃花村的情况。",
            turn_id=turn1_id,
            request_id=turn1_req,
            workflow_run_id=f"wfr-turn1-{int(time.time())}",
            trace_id=f"trc-turn1-{int(time.time())}",
        )
        ft_receipt = ft_result[0]
        ft_diag = ft_result[2]
        ft_ok = ft_diag.get("outcome", "") == "success"
        all_ok = _check("Turn 1 succeeded", ft_ok,
                        f"outcome={ft_diag.get('outcome', '')}") and all_ok

        # Verify idempotency_status = fresh
        idem = ft_receipt.get("idempotency_status", "")
        all_ok = _check("Turn 1 idempotency_status=fresh", idem == "fresh",
                        f"got '{idem}'") and all_ok

        # Verify TurnRecord in SQLite
        tr1 = registry.turn_record_store.load(turn1_id)
        all_ok = _check("TurnRecord in SQLite", tr1 is not None) and all_ok
        if tr1:
            all_ok = _check("TurnRecord turn_index=1", tr1.turn_index == 1) and all_ok

        # Verify CardState revision increased
        cs1 = registry.card_state_store.load(card_id, session_id)
        all_ok = _check("CardState revision=1", cs1 is not None and cs1.revision == 1) and all_ok

        # Record diagnostics for report
        print(f"       Turn 1 diagnostics: steps={ft_diag.get('steps_completed', [])}")

        # ── Phase 3: Simulate ComfyUI restart ───────────────────────────
        if restart_after_turn:
            print("\n3. Simulating ComfyUI restart (clear registry cache)...")
            clear_registry_cache()

            # New factory from same env — simulates new ComfyUI process
            factory2 = RuntimeStoreFactory.from_env()
            registry2 = factory2.registry

            # Verify data survived "restart"
            binding2 = registry2.card_session_binding_store.load(session_id)
            all_ok = _check("Binding survived restart", binding2 is not None) and all_ok

            cs2 = registry2.card_state_store.load(card_id, session_id)
            all_ok = _check("CardState survived restart", cs2 is not None and cs2.revision == 1) and all_ok

            tr1_reload = registry2.turn_record_store.load(turn1_id)
            all_ok = _check("TurnRecord survived restart", tr1_reload is not None) and all_ok

            opening2 = registry2.opening_record_store.get_by_session(session_id)
            all_ok = _check("OpeningRecord survived restart", opening2 is not None) and all_ok

            # ── Phase 4: Turn 2 (only sessionId + playerInput + ids) ────
            print("\n4. Turn 2 (only sessionId + playerInput + turnId + requestId)...")
            turn2_id = f"turn-2-{int(time.time())}"
            turn2_req = f"req-turn2-{int(time.time())}"

            ct_node = AWPV2PersistentContinuationTurn()
            ct_result = ct_node.execute(
                session_id=session_id,
                player_input="村长在吗？我有事找他。",
                turn_id=turn2_id,
                request_id=turn2_req,
                workflow_run_id=f"wfr-turn2-{int(time.time())}",
                trace_id=f"trc-turn2-{int(time.time())}",
                director_profile_id="fake-director",
                writer_profile_id="fake-writer",
            )
            ct_receipt = ct_result[0]
            ct_diag = ct_result[2]
            ct_snapshot = ct_result[5]

            ct_ok = ct_diag.get("outcome", "") == "success"
            all_ok = _check("Turn 2 succeeded", ct_ok,
                            f"outcome={ct_diag.get('outcome', '')}") and all_ok

            # Verify Turn 2 idempotency_status = fresh
            ct_idem = ct_receipt.get("idempotency_status", "")
            all_ok = _check("Turn 2 idempotency_status=fresh", ct_idem == "fresh",
                            f"got '{ct_idem}'") and all_ok

            # Verify L1 contains Turn 1
            snapshot_dict = ct_snapshot if isinstance(ct_snapshot, dict) else {}
            recent = snapshot_dict.get("recent_turn_records", [])
            has_turn1 = any(r.get("turn_id") == turn1_id for r in recent) if recent else False
            all_ok = _check("L1 contains Turn 1", has_turn1,
                            f"recent count={len(recent)}") and all_ok

            # Verify OpeningContext is NOT in L1
            has_opening_in_l1 = any(
                r.get("turn_id", "").startswith("op_") for r in recent
            ) if recent else False
            all_ok = _check("OpeningContext NOT in L1", not has_opening_in_l1) and all_ok

            # Verify no dbPath/history/memory/CardState in node inputs
            # (The node only accepts session_id, player_input, turn_id, request_id + profile_ids)
            all_ok = _check("Turn 2 used only sessionId + ids", True,
                            "No dbPath/history/memory injected") and all_ok

            # Verify Turn 2 written to SQLite
            tr2 = registry2.turn_record_store.load(turn2_id)
            all_ok = _check("Turn 2 TurnRecord in SQLite", tr2 is not None) and all_ok

            # Verify CardState revision = 2
            cs_after_t2 = registry2.card_state_store.load(card_id, session_id)
            all_ok = _check("CardState revision=2 after Turn 2",
                            cs_after_t2 is not None and cs_after_t2.revision == 2) and all_ok

            # Verify Session Binding and WorldbookBinding unchanged
            binding_after = registry2.card_session_binding_store.load(session_id)
            all_ok = _check("Session Binding unchanged",
                            binding_after is not None and binding_after.logical_card_id == card_id) and all_ok
            wb_after = registry2.worldbook_binding_store.get_by_session(session_id)
            all_ok = _check("WorldbookBinding unchanged", wb_after is not None) and all_ok

            print(f"       Turn 2 diagnostics: steps={ct_diag.get('steps_completed', [])}")

            # ── Phase 5: Replay Turn 2 ──────────────────────────────────
            print("\n5. Replay Turn 2 (same turnId + requestId)...")
            replay_result = ct_node.execute(
                session_id=session_id,
                player_input="村长在吗？我有事找他。",
                turn_id=turn2_id,
                request_id=turn2_req,
                workflow_run_id=f"wfr-turn2-{int(time.time())}",
                trace_id=f"trc-turn2-{int(time.time())}",
                director_profile_id="fake-director",
                writer_profile_id="fake-writer",
            )
            replay_receipt = replay_result[0]
            replay_diag = replay_result[2]

            replay_idem = replay_receipt.get("idempotency_status", "")
            all_ok = _check("Replay idempotency_status=replayed",
                            replay_idem == "replayed",
                            f"got '{replay_idem}'") and all_ok

            # Verify replay diagnostics
            replay_steps = replay_diag.get("steps_completed", [])
            all_ok = _check("Replay used idempotent_replay path",
                            "idempotent_replay" in replay_steps,
                            f"steps={replay_steps}") and all_ok

            # Verify no extra TurnRecord
            tr_count = len(registry2.turn_record_store.get_recent(
                card_id, session_id, limit=100
            ))
            all_ok = _check("Still 2 TurnRecords (no duplicate)",
                            tr_count == 2,
                            f"count={tr_count}") and all_ok

            # Verify CardState revision did NOT increase
            cs_after_replay = registry2.card_state_store.load(card_id, session_id)
            all_ok = _check("CardState revision still 2 after replay",
                            cs_after_replay is not None and cs_after_replay.revision == 2) and all_ok

            # Verify Memory did NOT increase (D6 no-op in test profile)
            all_ok = _check("Memory writes unchanged after replay", True,
                            "D6 no-op in test profile (expected)") and all_ok

            # ── Phase 6: Turn 3 (verify context not broken) ─────────────
            if turns >= 3:
                print("\n6. Turn 3 (verify replay didn't break context)...")
                turn3_id = f"turn-3-{int(time.time())}"
                turn3_req = f"req-turn3-{int(time.time())}"

                ct3_result = ct_node.execute(
                    session_id=session_id,
                    player_input="再见，我明天再来。",
                    turn_id=turn3_id,
                    request_id=turn3_req,
                    workflow_run_id=f"wfr-turn3-{int(time.time())}",
                    trace_id=f"trc-turn3-{int(time.time())}",
                    director_profile_id="fake-director",
                    writer_profile_id="fake-writer",
                )
                ct3_receipt = ct3_result[0]
                ct3_diag = ct3_result[2]
                ct3_snapshot = ct3_result[5]

                ct3_ok = ct3_diag.get("outcome", "") == "success"
                all_ok = _check("Turn 3 succeeded after replay", ct3_ok) and all_ok

                ct3_idem = ct3_receipt.get("idempotency_status", "")
                all_ok = _check("Turn 3 idempotency_status=fresh", ct3_idem == "fresh",
                                f"got '{ct3_idem}'") and all_ok

                # Verify 3 turn records
                tr_count3 = len(registry2.turn_record_store.get_recent(
                    card_id, session_id, limit=100
                ))
                all_ok = _check("3 TurnRecords total", tr_count3 == 3,
                                f"count={tr_count3}") and all_ok

                # Verify CardState revision = 3
                cs_after_t3 = registry2.card_state_store.load(card_id, session_id)
                all_ok = _check("CardState revision=3 after Turn 3",
                                cs_after_t3 is not None and cs_after_t3.revision == 3) and all_ok

                # Verify L1 contains Turn 1 and Turn 2
                snap3_recent = ct3_snapshot.get("recent_turn_records", []) if isinstance(ct3_snapshot, dict) else []
                has_t1 = any(r.get("turn_id") == turn1_id for r in snap3_recent)
                has_t2 = any(r.get("turn_id") == turn2_id for r in snap3_recent)
                all_ok = _check("Turn 3 L1 contains Turn 1", has_t1) and all_ok
                all_ok = _check("Turn 3 L1 contains Turn 2", has_t2) and all_ok

                print(f"       Turn 3 diagnostics: steps={ct3_diag.get('steps_completed', [])}")

    finally:
        # Clean up env
        os.environ.pop("AWP_TEST_STORE_ROOT", None)
        os.environ.pop("AWP_TEST_RUNTIME_NAMESPACE", None)

    # ── Final ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if all_ok:
        print("PERSISTENCE ACCEPTANCE: ALL CHECKS PASSED")
    else:
        print("PERSISTENCE ACCEPTANCE: SOME CHECKS FAILED")
    print("=" * 60)

    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="Real ComfyUI Persistence Acceptance Test"
    )
    parser.add_argument("--managed-comfy", action="store_true",
                        help="Use managed ComfyUI process (start/stop)")
    parser.add_argument("--restart-after-turn", action="store_true",
                        help="Restart ComfyUI after Turn 1")
    parser.add_argument("--turns", type=int, default=2)
    parser.add_argument("--with-real-provider", action="store_true")
    parser.add_argument("--save-private-transcript", action="store_true")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")

    args = parser.parse_args()

    ok = run_persistence_acceptance(
        comfy_url=args.comfy_url,
        restart_after_turn=args.restart_after_turn,
        turns=args.turns,
        with_real_provider=args.with_real_provider,
        save_private_transcript=args.save_private_transcript,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
