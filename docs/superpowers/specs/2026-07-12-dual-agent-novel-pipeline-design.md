# Dual-Agent Novel Pipeline Design

## Goal

Restore the original two-agent contract: the Plan Agent reads broad project context and produces a compact chapter contract; the Writer Agent receives only the information needed to write one fluent chapter.

## Boundaries

- Keep the synchronous Python novel pipeline.
- Keep one full-chapter Writer call to preserve prose flow.
- Do not restore the Director LLM.
- Do not change RP mode.
- Only deterministic runtimes may persist drafts, ledger, and memory.

## Data Flow

```text
project + volume + outline + story bible + world + ledger + prior summaries
                              |
                              v
                         Plan Agent
                              |
                              v
                         ChapterPlan
                              |
                              v
                NovelWriterContextCompiler
                 /       |        |       \
          cast allowlist world  history  contract
                              |
                              v
                      Single-pass Writer
                              |
                              v
              PlanAdherenceChecker + Quality
                              |
                              v
                     Draft + Ledger update
```

## Chapter Contract

The Writer receives a medium-granularity contract rather than the entire planning corpus or a scene-by-scene screenplay:

- chapter title, position, target emotion, and target length;
- opening state;
- two to four narrative moves derived from `scene_beats`;
- required turning point, payoff, and ending state;
- allowed cast and relationship change;
- explicit boundaries for events and characters that must not appear early.

The contract may describe goals, obstacles, actions, and outcomes. It must not prescribe exact dialogue, micro-expressions, prose sentences, or fixed paragraph layouts.

## Context Policy

- Writer receives the previous chapter tail.
- Writer receives the latest three chapter summaries verbatim and older summaries through a compact history section.
- Writer receives only world rules relevant to the chapter, with a small always-on foundation fallback.
- Writer receives only character cards named by `character_appearance.appearance_order`.
- `first_appearance <= 0` means “not scheduled”, not “already appeared”.
- Story Bible is Plan-only by default. Chapter-specific guidance may reach Writer separately.
- Raw active memory and RAG recall remain outside the Writer prompt until a tested selection policy exists.

## Validation

Deterministic checks run before persistence:

- every planned cast name must exist in the project character registry;
- unauthorized known characters appearing in the draft are blocking;
- required turning point, climax/payoff, and ending are checked through compact semantic claims;
- missing plan coverage produces a rejected draft rather than silently accepted output;
- validation diagnostics are attached to `QualityDecision` warnings/blocking reasons.

## Non-goals

- Guaranteeing subjective literary quality.
- Sending every prior chapter summary forever.
- Enforcing exact dialogue or exact beat word counts.
- Adding Pi, async execution, or another LLM agent.

## Success Criteria

- Writer prompt contains all chapter beats, turning point, climax, ending, and allowed cast.
- Writer prompt excludes unplanned character cards and the full Story Bible.
- World constraints are present and bounded.
- A draft that omits the central planned payoff is rejected by deterministic plan-adherence checks.
- A draft containing a known unauthorized character is rejected.
- Existing novel beat-continuity tests remain green.
