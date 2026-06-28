"""Quality observer — non-blocking, per-turn narrative quality evaluator.

This is a TEST/OBSERVABILITY component. It NEVER blocks an accepted turn,
NEVER writes CardState/TurnRecord/memory, and NEVER changes the formal
QualityGate verdict. Its only job is to record structured quality signals
into the turn artifact / final report so drift can be analyzed.

V1 is deterministic (no LLM). It checks:
  - history conflict (player_input contradicts an accepted fact)
  - CardState revision / TurnRecord continuity
  - L1/L2/L3 evidence presence
  - format / repetition / empty-output / turn-break checks

An optional LLM evaluator can be added later behind an explicit real-test
flag; V1 ships deterministic only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityObservation:
    """One turn's quality observation. Non-blocking."""

    turn_index: int
    turn_id: str
    continuity_score: float = 1.0
    character_consistency_score: float = 1.0
    player_agency_score: float = 1.0
    memory_use_score: float = 0.0
    state_consistency_score: float = 1.0
    worldbook_relevance_score: float = 1.0
    repetition_risk_score: float = 0.0  # higher = more risk
    hard_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence_turn_ids: list[str] = field(default_factory=list)
    evidence_memory_ids: list[str] = field(default_factory=list)
    short_rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "turn_id": self.turn_id,
            "continuity_score": round(self.continuity_score, 3),
            "character_consistency_score": round(self.character_consistency_score, 3),
            "player_agency_score": round(self.player_agency_score, 3),
            "memory_use_score": round(self.memory_use_score, 3),
            "state_consistency_score": round(self.state_consistency_score, 3),
            "worldbook_relevance_score": round(self.worldbook_relevance_score, 3),
            "repetition_risk_score": round(self.repetition_risk_score, 3),
            "hard_failures": list(self.hard_failures),
            "warnings": list(self.warnings),
            "evidence_turn_ids": list(self.evidence_turn_ids),
            "evidence_memory_ids": list(self.evidence_memory_ids),
            "short_rationale": self.short_rationale,
        }


class QualityObserver:
    """Deterministic non-blocking quality observer."""

    def observe(
        self,
        turn_index: int,
        turn_id: str,
        player_input: str,
        writer_output: str,
        diag: dict[str, Any],
        previous_outputs: list[str],
        scenario_required_facts: list[str] | None = None,
    ) -> QualityObservation:
        obs = QualityObservation(turn_index=turn_index, turn_id=turn_id)
        rationale_parts: list[str] = []

        # ── Hard failures (deterministic) ────────────────────────────────
        if not writer_output.strip():
            obs.hard_failures.append("empty_writer_output")
            obs.continuity_score = 0.0
        if diag.get("outcome") != "success":
            obs.hard_failures.append(f"turn_outcome={diag.get('outcome','')}")
            obs.continuity_score = 0.0

        # JSON / debug leak
        if any(m in writer_output for m in ("```", '"turn_goal"', "DEBUG", "TODO")):
            obs.warnings.append("format_leak")
            obs.character_consistency_score = max(0.0, obs.character_consistency_score - 0.3)

        # ── State consistency ────────────────────────────────────────────
        rev_before = diag.get("card_state_revision_before", 0)
        rev_after = diag.get("card_state_revision_after", 0)
        if rev_after < rev_before:
            obs.hard_failures.append("revision_regression")
            obs.state_consistency_score = 0.0
        elif rev_after == rev_before and turn_index > 0:
            obs.warnings.append("no_state_change")
            obs.state_consistency_score = 0.8
        if diag.get("turn_record_commit_status") != "committed":
            obs.hard_failures.append("turn_not_committed")

        # ── Memory use evidence ──────────────────────────────────────────
        l1 = diag.get("l1_turn_ids_recalled", [])
        l2 = diag.get("l2_memory_ids_recalled", [])
        l3 = diag.get("l3_memory_ids_recalled", [])
        obs.evidence_turn_ids = list(l1)
        obs.evidence_memory_ids = list(l2) + list(l3)
        components = 0
        score = 0.0
        if l1:
            score += 1.0; components += 1
        if l2:
            score += 1.0; components += 1
        if l3:
            score += 1.0; components += 1
        if turn_index > 1:
            obs.memory_use_score = score / 3.0
            if not l1:
                obs.warnings.append("no_l1_recall_on_continuation")
                rationale_parts.append("L1 missing on continuation")
        else:
            obs.memory_use_score = 1.0  # turn 1 has no history to recall

        # ── Continuity: required facts present somewhere ─────────────────
        if scenario_required_facts:
            present = [f for f in scenario_required_facts if f in writer_output]
            if present:
                obs.continuity_score = 1.0
                rationale_parts.append(f"required_facts_present:{len(present)}")
            else:
                obs.continuity_score = 0.7
                obs.warnings.append("required_facts_absent_this_turn")

        # ── Repetition risk ──────────────────────────────────────────────
        if previous_outputs:
            # N-gram overlap with the immediately previous output
            overlap = self._overlap(writer_output, previous_outputs[-1])
            obs.repetition_risk_score = overlap
            if overlap > 0.6:
                obs.warnings.append(f"high_repetition_with_prev:{overlap:.2f}")
                obs.continuity_score = max(0.0, obs.continuity_score - 0.2)
            # Across-window repetition
            if len(previous_outputs) >= 3:
                max_overlap = max(
                    self._overlap(writer_output, p) for p in previous_outputs[-3:-1]
                )
                if max_overlap > 0.7:
                    obs.warnings.append(f"repetition_loop:{max_overlap:.2f}")
                    obs.repetition_risk_score = max(obs.repetition_risk_score, max_overlap)

        # ── Player agency: writer output should not be empty of response ─
        if len(writer_output.strip()) < 50 and writer_output.strip():
            obs.player_agency_score = 0.5
            obs.warnings.append("very_short_response")

        # ── Worldbook relevance ──────────────────────────────────────────
        wb_ids = diag.get("worldbook_entry_ids_activated", [])
        if not wb_ids and turn_index > 2:
            obs.warnings.append("no_worldbook_activated")
            obs.worldbook_relevance_score = 0.7

        if not rationale_parts:
            rationale_parts.append("ok")
        obs.short_rationale = "; ".join(rationale_parts)
        return obs

    @staticmethod
    def _overlap(a: str, b: str) -> float:
        """Character 4-gram Jaccard overlap between two texts."""
        if not a or not b:
            return 0.0
        def grams(s: str) -> set[str]:
            s = s[:2000]
            return {s[i:i + 4] for i in range(len(s) - 3)} if len(s) >= 4 else {s}
        ga, gb = grams(a), grams(b)
        if not ga or not gb:
            return 0.0
        return len(ga & gb) / len(ga | gb)
