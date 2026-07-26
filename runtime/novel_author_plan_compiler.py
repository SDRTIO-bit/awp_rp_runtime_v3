"""Deterministically compile an approved author plan for the Writer."""

from __future__ import annotations

from ..contracts.novel_authoring import AuthorChapterPlan, AuthorPlanStatus
from ..contracts.novel_chapter import (
    BeatDetail,
    ChapterPlan,
    CharacterAppearance,
    ContentSummary,
    EndingDesign,
    PlotArrangement,
)


class AuthorPlanCompiler:
    """Mechanical mapping only: no model, role runtime, or creative expansion."""

    def compile(self, plan: AuthorChapterPlan) -> ChapterPlan:
        self._validate(plan)
        scene_count = len(plan.scenes)
        base_budget = max(1, plan.target_chars // scene_count)
        remainder = plan.target_chars - base_budget * scene_count
        beats = tuple(
            BeatDetail(
                beat_id=scene.scene_id,
                description=f"{scene.summary}；变化：{scene.change}",
                function_tag=scene.purpose or "作者确定场景",
                density="normal",
                budget_chars=base_budget + (remainder if index == scene_count else 0),
            )
            for index, scene in enumerate(plan.scenes, start=1)
        )
        characters = tuple(
            dict.fromkeys(
                [
                    *(
                        name
                        for scene in plan.scenes
                        for name in scene.characters
                    ),
                    *(intent.character for intent in plan.character_intents),
                ]
            )
        )
        changes = tuple(scene.change for scene in plan.scenes if scene.change)
        ending_state = (
            plan.scenes[-1].ending_state
            or plan.scenes[-1].change
        )
        events = list(plan.confirmed_events)
        return ChapterPlan(
            chapter_id=(
                f"author-{plan.project_id}-ch{plan.chapter_index}-v{plan.revision}"
            ),
            project_id=plan.project_id,
            chapter_index=plan.chapter_index,
            title=plan.title or f"第{plan.chapter_index}章",
            target_chars=plan.target_chars,
            target_emotion=plan.target_reader_effect,
            main_payoff=plan.purpose,
            content_summary=ContentSummary(
                cause=events[0] if events else "",
                development="；".join(events[1:]),
                turning_point="；".join(plan.causal_chain),
                climax=plan.purpose,
                ending=ending_state,
            ),
            plot_arrangement=PlotArrangement(
                main_line="；".join(events),
                emotion_line="；".join(changes),
                logic_line="；".join(plan.causal_chain),
            ),
            character_appearance=CharacterAppearance(
                appearance_order=characters,
                relationship_changes=changes,
                information_gap="；".join(plan.information_distribution),
            ),
            scene_beats=beats,
            ending_design=EndingDesign(
                closing_state=ending_state,
                open_questions=tuple(plan.deliberate_ambiguities),
                hook_type="",
                hook_detail="",
                hook_strength="weak",
            ),
        )

    def compile_and_save(self, plan: AuthorChapterPlan, registry) -> ChapterPlan:
        self._validate_characters(plan, registry)
        chapter = self.compile(plan)
        registry.novel_chapter_plan_store.save(chapter)
        return chapter

    def render_writer_contract(self, plan: AuthorChapterPlan) -> str:
        self._validate(plan)

        def section(title: str, values: list[str]) -> list[str]:
            return [f"{title}：", *(f"- {value}" for value in values)] if values else []

        lines = [
            "[AUTHOR-APPROVED]",
            f"作者计划：{plan.plan_id} v{plan.revision}",
            f"本章存在理由：{plan.purpose}",
        ]
        if plan.target_reader_effect:
            lines.append(f"目标读者效果：{plan.target_reader_effect}")
        lines.extend(section("确定事件（按作者给定顺序）", plan.confirmed_events))
        lines.extend(
            section(
                "场景（不得增删或调换）",
                [f"{scene.summary}；变化：{scene.change}" for scene in plan.scenes],
            )
        )
        lines.extend(section("因果关系", plan.causal_chain))
        lines.extend(section("世界与连续性约束", plan.world_constraints))
        lines.extend(section("信息分配", plan.information_distribution))
        lines.extend(section("必须保留", plan.must_keep))
        lines.extend(section("明确禁止", plan.must_not))
        lines.extend(section("有意保留的歧义或不适", plan.deliberate_ambiguities))
        lines.extend(section("Writer 可自由发挥", plan.writer_freedom))
        for intent in plan.character_intents:
            lines.append(
                f"人物意图·{intent.character}：目标={intent.goal}；"
                f"动机={intent.motivation}；选择={intent.choice}；潜台词={intent.subtext}"
            )
            lines.extend(section(f"{intent.character} 性格边界", intent.boundaries))
        return "\n".join(lines)

    @staticmethod
    def _validate(plan: AuthorChapterPlan) -> None:
        if plan.status not in {AuthorPlanStatus.APPROVED, AuthorPlanStatus.EXECUTED}:
            raise ValueError("author plan must be approved before compilation")
        if plan.unresolved_questions:
            raise ValueError("author plan contains unresolved questions")
        if not plan.scenes:
            raise ValueError("author plan has no scenes")

    @staticmethod
    def _validate_characters(plan: AuthorChapterPlan, registry) -> None:
        known = {
            character.name
            for character in registry.novel_character_store.list_by_project(
                plan.project_id
            )
        }
        explicitly_new = {
            intent.character
            for intent in plan.character_intents
            if intent.new_character
        }
        referenced = {
            *(name for scene in plan.scenes for name in scene.characters),
            *(intent.character for intent in plan.character_intents),
        }
        unknown = referenced - known - explicitly_new
        if unknown:
            raise ValueError(
                "author plan references unknown characters: "
                + ", ".join(sorted(unknown))
            )


__all__ = ["AuthorPlanCompiler"]
