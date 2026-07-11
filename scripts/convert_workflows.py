"""Convert AWP workflows to proper ComfyUI graph format with I/O."""
import json, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from awp_rp_runtime_v3.nodes import NODE_CLASS_MAPPINGS


def build_graph(nodes_spec):
    """Build ComfyUI graph format from a compact node spec.

    nodes_spec: list of (node_id, class_type, title, inputs_dict)
    inputs_dict values: literal value or (src_id, src_slot) for links
    """
    node_map = {}
    for nid, ct, title, inputs in nodes_spec:
        node_map[nid] = {"class_type": ct, "_meta": {"title": title}, "inputs": inputs}

    # Build adjacency
    children = {nid: [] for nid in node_map}
    parents = {nid: [] for nid in node_map}
    for nid, ndata in node_map.items():
        for inp_val in ndata.get('inputs', {}).values():
            if isinstance(inp_val, (list, tuple)) and len(inp_val) == 2 and isinstance(inp_val[0], int):
                pid = inp_val[0]
                if pid in children:
                    children[pid].append(nid)
                    parents[nid].append(pid)

    # Topological BFS
    roots = [nid for nid in node_map if not parents.get(nid)] or list(node_map.keys())[:1]
    visited, layers, queue = set(), [], list(roots)
    while queue:
        layer, nxt = [], []
        for nid in queue:
            if nid not in visited:
                visited.add(nid)
                layer.append(nid)
                for c in children.get(nid, []):
                    if c not in visited:
                        nxt.append(c)
        if layer:
            layers.append(layer)
        queue = nxt
    unvisited = [nid for nid in node_map if nid not in visited]
    if unvisited:
        layers.append(unvisited)

    x_gap, y_gap = 380, 160
    x_pos = {nid: 80 + li * x_gap for li, layer in enumerate(layers) for ni, nid in enumerate(layer)}
    y_pos = {nid: 80 + ni * y_gap for li, layer in enumerate(layers) for ni, nid in enumerate(layer)}

    # Slot maps
    input_slot_map = {}
    output_slot_map = {}
    for nid, ndata in node_map.items():
        ct = ndata['class_type']
        cls = NODE_CLASS_MAPPINGS.get(ct)
        if cls:
            try:
                it = cls.INPUT_TYPES()
                names = list(it.get('required', {}).keys()) + list(it.get('optional', {}).keys())
                input_slot_map[nid] = {n: i for i, n in enumerate(names)}
            except Exception:
                input_slot_map[nid] = {}
            try:
                output_slot_map[nid] = {n: i for i, n in enumerate(cls.RETURN_NAMES)}
            except Exception:
                output_slot_map[nid] = {}

    # Build links
    link_id = 1
    links = []
    node_inputs_ui = {}
    node_outputs_ui = {}

    for nid in sorted(node_map.keys()):
        ndata = node_map[nid]
        ct = ndata['class_type']
        inputs = ndata.get('inputs', {})
        sm = input_slot_map.get(nid, {})
        ui_inputs = []

        for inp_name, inp_val in inputs.items():
            slot_idx = sm.get(inp_name, 0)
            if isinstance(inp_val, (list, tuple)) and len(inp_val) == 2 and isinstance(inp_val[0], int):
                src_node = inp_val[0]
                src_slot = inp_val[1]
                link_type = "ANY"
                src_ct = node_map.get(src_node, {}).get('class_type', '')
                src_cls = NODE_CLASS_MAPPINGS.get(src_ct)
                if src_cls:
                    try:
                        rt = src_cls.RETURN_TYPES
                        if src_slot < len(rt):
                            link_type = rt[src_slot]
                    except Exception:
                        pass
                ui_inputs.append({"name": inp_name, "type": link_type, "link": link_id})
                links.append([link_id, src_node, src_slot, nid, slot_idx, link_type])
                link_id += 1
            else:
                ui_inputs.append({"name": inp_name, "type": "STRING", "link": None})
        node_inputs_ui[nid] = ui_inputs

        cls = NODE_CLASS_MAPPINGS.get(ct)
        ui_outputs = []
        if cls:
            try:
                for oi, (otype, oname) in enumerate(zip(cls.RETURN_TYPES, cls.RETURN_NAMES)):
                    ui_outputs.append({"name": oname, "type": otype, "links": [], "slot_index": oi})
            except Exception:
                pass
        node_outputs_ui[nid] = ui_outputs

    # Fill output links
    for lid, src, sslot, dst, dslot, ltype in links:
        for out in node_outputs_ui.get(src, []):
            if out.get("slot_index") == sslot:
                out.setdefault("links", []).append(lid)
                break

    # Build nodes
    nodes = []
    for nid in sorted(node_map.keys()):
        ndata = node_map[nid]
        ct = ndata['class_type']
        meta = ndata.get('_meta', {'title': ct})
        ni = node_inputs_ui[nid]
        no = node_outputs_ui[nid]
        nodes.append({
            "id": nid,
            "type": ct,
            "pos": [x_pos.get(nid, 100), y_pos.get(nid, 100)],
            "size": [300, max(80, 26 * max(len(ni), len(no), 1))],
            "flags": {},
            "order": nid,
            "mode": 0,
            "inputs": ni,
            "outputs": no,
            "properties": {},
            "_meta": meta,
        })

    return {
        "last_node_id": max(node_map.keys()) if node_map else 0,
        "last_link_id": link_id - 1,
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }


def save_workflow(path, spec, metadata=None):
    data = build_graph(spec)
    if metadata:
        for k, v in metadata.items():
            data[k] = v
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'{os.path.basename(path)}: {len(data["nodes"])} nodes, {len(data["links"])} links')


def main():
    base = os.path.join(os.path.dirname(__file__), '..', 'workflows', 'api')

    # =========================================================================
    # 1. bootstrap_only — Import card + create session
    # =========================================================================
    save_workflow(os.path.join(base, 'bootstrap_only.api.json'), [
        (1, "AWPV2PersistentBootstrap", "导入角色卡 + 创建会话", {
            "source_path": "C:\\path\\to\\card.json",
            "session_id": "my-session-001",
            "greeting_id": "g0",
            "request_id": "req-bootstrap-001",
            "run_id": "run-001",
        }),
        (2, "AWPV2TraceDisplay", "Bootstrap 诊断", {
            "data": (1, 4),
            "label": "Bootstrap Diagnostics",
        }),
    ], {"_comment": "Bootstrap: 导入角色卡 + 创建 SQLite 会话。先运行这个，再运行其他工作流。"})

    # =========================================================================
    # 2. persistent_play_session — Production: Bootstrap + Turn1 + Continue
    # =========================================================================
    save_workflow(os.path.join(base, 'persistent_play_session.api.json'), [
        # Bootstrap
        (1, "AWPV2PersistentBootstrap", "导入角色卡 + 创建会话", {
            "source_path": "C:\\path\\to\\card.json",
            "session_id": "my-session-001",
            "greeting_id": "g0",
            "request_id": "req-bootstrap-001",
            "run_id": "run-001",
        }),
        # Turn 1
        (2, "AWPV2PersistentFirstTurn", "回合1: 玩家首回合", {
            "session_id": "my-session-001",
            "player_input": "我推开院门，看见一个穿粗布衣裳的年轻女子在井边打水。",
            "turn_id": "turn-001",
            "request_id": "req-turn-001",
            "director_profile_id": "deepseek-v4-flash-director",
            "writer_profile_id": "deepseek-v4-pro-writer",
        }),
        # Continue (world advance)
        (3, "AWPV2ContinueTurnP1", "回合2: 世界推进 (无需玩家输入)", {
            "session_id": "my-session-001",
            "turn_id": "turn-002",
            "request_id": "req-turn-002",
            "director_profile_id": "deepseek-v4-flash-director",
            "writer_profile_id": "deepseek-v4-pro-writer",
        }),
        # Output: Turn 1 text
        (10, "AWPV2AcceptedTextOutput", "【输出】回合1 正文", {
            "turn_record": (2, 4),
        }),
        # Output: Turn 1 probe
        (11, "AWPV2TurnResultProbe", "【输出】回合1 结果", {
            "receipt": (2, 0),
            "diagnostics": (2, 2),
            "turn_record": (2, 4),
            "turn_kind": "first",
        }),
        # Output: Turn 2 text
        (12, "AWPV2AcceptedTextOutput", "【输出】回合2 正文", {
            "turn_record": (3, 4),
        }),
        # Output: Turn 2 probe
        (13, "AWPV2TurnResultProbe", "【输出】回合2 结果", {
            "receipt": (3, 0),
            "diagnostics": (3, 2),
            "turn_record": (3, 4),
            "turn_kind": "continuation",
        }),
        # Bootstrap diagnostics
        (14, "AWPV2TraceDisplay", "Bootstrap 诊断", {
            "data": (1, 4),
            "label": "Bootstrap",
        }),
    ], {"_comment": "生产工作流: Bootstrap + 首回合 + 世界推进。修改 player_input 和 session_id 后运行。"})

    # =========================================================================
    # 3. continuation_turn_only — Add more turns after bootstrap+first
    # =========================================================================
    save_workflow(os.path.join(base, 'continuation_turn_only.api.json'), [
        # Player input turn
        (1, "AWPV2PersistentContinuationTurn", "玩家输入回合", {
            "session_id": "my-session-001",
            "player_input": "那女子抬起头，竟是周语晴。她眼圈一红：你总算回来了。",
            "turn_id": "turn-003",
            "request_id": "req-turn-003",
            "director_profile_id": "deepseek-v4-flash-director",
            "writer_profile_id": "deepseek-v4-pro-writer",
        }),
        # World advance turn
        (2, "AWPV2ContinueTurnP1", "世界推进回合", {
            "session_id": "my-session-001",
            "turn_id": "turn-004",
            "request_id": "req-turn-004",
            "director_profile_id": "deepseek-v4-flash-director",
            "writer_profile_id": "deepseek-v4-pro-writer",
        }),
        # Outputs
        (10, "AWPV2AcceptedTextOutput", "【输出】玩家回合正文", {
            "turn_record": (1, 4),
        }),
        (11, "AWPV2TurnResultProbe", "【输出】玩家回合结果", {
            "receipt": (1, 0),
            "diagnostics": (1, 2),
            "turn_record": (1, 4),
            "turn_kind": "continuation",
        }),
        (12, "AWPV2AcceptedTextOutput", "【输出】推进回合正文", {
            "turn_record": (2, 4),
        }),
        (13, "AWPV2TurnResultProbe", "【输出】推进回合结果", {
            "receipt": (2, 0),
            "diagnostics": (2, 2),
            "turn_record": (2, 4),
            "turn_kind": "continuation",
        }),
        (14, "AWPV2TraceDisplay", "玩家回合上下文", {
            "data": (1, 1),
            "label": "Continuation Context",
        }),
        (15, "AWPV2TraceDisplay", "推进回合上下文", {
            "data": (2, 1),
            "label": "Continue Context",
        }),
    ], {"_comment": "连续回合: 修改 player_input 和 turn_id 后运行。需要先完成 bootstrap + first turn。"})

    # =========================================================================
    # 4. full_architecture_turn — Explicit architecture with all sub-agents
    # =========================================================================
    save_workflow(os.path.join(base, 'full_architecture_turn.api.json'), [
        # Phase 1: Load + Director + Tools
        (1, "AWPV2SessionRuntimeLoad", "加载会话状态 (L0-L3)", {
            "session_id": "my-session-001",
            "player_input": "我推开院门，看见一个穿粗布衣裳的年轻女子在井边打水。",
        }),
        (2, "AWPV2RoundSnapshot", "回合快照 (含世界书+记忆)", {
            "card_state": (1, 1),
            "player_input": "我推开院门，看见一个穿粗布衣裳的年轻女子在井边打水。",
            "worldbook_entries": (1, 3),
        }),
        (3, "AWPV2DirectorPlan", "Director: 叙事规划", {
            "round_snapshot": (2, 0),
        }),
        (4, "AWPV2ToolGateway", "工具网关 (世界书查询等)", {
            "tool_plan": (3, 1),
            "round_snapshot": (2, 0),
        }),
        (5, "AWPV2EnrichmentMerge", "工具结果合并", {
            "tool_result_bundle": (4, 0),
        }),

        # Phase 2: D1 History Recall
        (10, "AWPV2HistoryRecallTrigger", "D1 触发: 历史回查条件", {
            "snapshot": (2, 0),
            "director_plan": (3, 0),
        }),
        (11, "AWPV2HistoryRecallAgent", "D1 Agent: 历史证据分析", {
            "snapshot": (2, 0),
            "trigger_result": (10, 0),
        }),
        (12, "AWPV2HistoryRecallResult", "D1 结果: 排序后的历史证据", {
            "history_recall_result": (11, 0),
        }),

        # Phase 2: D2 Opportunity
        (13, "AWPV2OpportunityTrigger", "D2 触发: 戏剧机会条件", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
        }),
        (14, "AWPV2OpportunityAgent", "D2 Agent: 戏剧机会识别", {
            "round_snapshot": (2, 0),
            "trigger_result": (13, 0),
        }),
        (15, "AWPV2OpportunityResult", "D2 结果: 戏剧机会建议", {
            "opportunity_result": (14, 0),
        }),

        # Phase 2: D3 World-Life
        (16, "AWPV2WorldLifeTrigger", "D3 触发: 世界活性条件", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
            "opportunity_result": (15, 0),
        }),
        (17, "AWPV2WorldLifeAgent", "D3 Agent: 世界活性事件", {
            "round_snapshot": (2, 0),
            "trigger_result": (16, 0),
        }),
        (18, "AWPV2WorldLifeResult", "D3 结果: NPC/事件/环境", {
            "world_life_result": (17, 0),
        }),

        # Phase 2: D4 Emotion/Relationship
        (19, "AWPV2EmotionRelationshipTrigger", "D4 触发: 情绪关系条件", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
        }),
        (20, "AWPV2EmotionRelationshipAgent", "D4 Agent: 情绪关系解读", {
            "round_snapshot": (2, 0),
            "er_trigger_result": (19, 0),
        }),

        # Phase 3: D5 Continuity (Wave B)
        (21, "AWPV2ContinuityTrigger", "D5 触发: 连续性条件 (Wave B)", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
            "opportunity_result": (15, 0),
        }),
        (22, "AWPV2ContinuityAgent", "D5 Agent: 连续性约束", {
            "round_snapshot": (2, 0),
            "trigger_result": (21, 0),
        }),
        (23, "AWPV2ContinuityResult", "D5 结果: 连续性约束", {
            "continuity_result": (22, 0),
        }),

        # Phase 4: Merge + Write
        (24, "AWPV2SuggestionMerge", "子 Agent 建议合并", {
            "delegation_plan": (3, 2),
            "turn_brief": (3, 0),
            "round_snapshot": (2, 0),
            "execution_results": (3, 2),
        }),
        (25, "AWPV2FinalTurnBrief", "最终回合简报", {
            "director_plan": (3, 0),
            "enrichment_bundle": (5, 0),
            "round_snapshot": (2, 0),
        }),
        (26, "AWPV2WriterInputBundleV2", "Writer 输入包", {
            "round_snapshot": (2, 0),
            "final_turn_brief": (25, 0),
            "suggestion_merge_result": (24, 0),
        }),
        (27, "AWPV2WriterGenerate", "Writer: 生成 RP 正文", {
            "writer_input_bundle": (26, 0),
            "profile_id": "deepseek-v4-pro-writer",
        }),
        (28, "AWPV2QualityPipeline", "质量检查", {
            "writer_draft": (27, 0),
            "round_snapshot": (2, 0),
        }),
        (29, "AWPV2Reviser", "修订器 (质量不通过时)", {
            "writer_draft": (27, 0),
            "quality_decision": (28, 0),
            "writer_input_bundle": (26, 0),
        }),
        (30, "AWPV2WriterOutput", "提取最终正文", {
            "writer_draft": (29, 0),
        }),

        # Phase 5: Commit
        (31, "AWPV2CardStateCommit", "CardState 提交 (SQLite)", {
            "state_update_proposal": (28, 0),
            "quality_decision": (28, 0),
            "expected_revision": 0,
            "patch_id": "arch-turn-001-patch",
        }),
        (32, "AWPV2TurnRecordCommit", "回合记录提交 (SQLite)", {
            "player_input": "我推开院门，看见一个穿粗布衣裳的年轻女子在井边打水。",
            "accepted_text": (30, 0),
            "round_snapshot": (2, 0),
            "quality_decision": (28, 0),
            "base_card_state_revision": 0,
            "result_card_state_revision": 0,
        }),
        (33, "AWPV2MemoryCuratorAgent", "D6 Agent: 记忆治理", {
            "quality_decision": (28, 0),
            "turn_record": (32, 0),
            "round_snapshot": (2, 0),
            "card_state_commit_result": (31, 0),
        }),
        (34, "AWPV2MemoryCommitPlan", "记忆提交计划", {
            "round_snapshot": (2, 0),
            "accepted_text": (30, 0),
            "quality_decision": (28, 0),
            "turn_id": "arch-turn-001",
        }),
        (35, "AWPV2ActiveMemoryCommit", "L2 活跃记忆提交", {
            "memory_commit_plan": (34, 0),
            "quality_decision": (28, 0),
            "card_state_commit_result": (31, 0),
            "turn_record_commit_result": (32, 0),
        }),
        (36, "AWPV2RagMemoryCommit", "L3 RAG 记忆提交", {
            "memory_commit_plan": (34, 0),
            "quality_decision": (28, 0),
            "card_state_commit_result": (31, 0),
            "turn_record_commit_result": (32, 0),
        }),

        # Outputs
        (90, "AWPV2AcceptedTextOutput", "【输出】RP 正文", {
            "turn_record": (32, 0),
        }),
        (91, "AWPV2TurnResultProbe", "【输出】回合结果", {
            "receipt": (31, 0),
            "turn_record": (32, 0),
            "turn_kind": "continuation",
        }),
        (92, "AWPV2TraceDisplay", "【输出】Director 计划", {
            "data": (3, 0),
            "label": "Director Plan",
        }),
        (93, "AWPV2TraceDisplay", "【输出】世界书 (RoundSnapshot)", {
            "data": (2, 0),
            "label": "RoundSnapshot (含世界书+历史+记忆)",
        }),
        (94, "AWPV2TraceDisplay", "【输出】D6 记忆治理", {
            "data": (33, 0),
            "label": "Memory Curation",
        }),
        (95, "AWPV2TraceDisplay", "【输出】工具追踪", {
            "data": (4, 1),
            "label": "Tool Execution Trace",
        }),
    ], {
        "_comment": "完整架构显式连线: Director + Writer 双Agent, D1-D6 子Agent, ToolGateway, 质量门, 状态/记忆提交。",
        "_usage": "需要先 bootstrap 会话。修改 session_id 和 player_input 后运行。",
    })

    # =========================================================================
    # 5. sub_agents_only — Isolated D1-D6 chain
    # =========================================================================
    save_workflow(os.path.join(base, 'sub_agents_only.api.json'), [
        # Load + Director
        (1, "AWPV2SessionRuntimeLoad", "加载会话状态", {
            "session_id": "my-session-001",
            "player_input": "我推开门，屋内一片漆黑。",
        }),
        (2, "AWPV2RoundSnapshot", "回合快照", {
            "card_state": (1, 1),
            "player_input": "我推开门，屋内一片漆黑。",
            "worldbook_entries": (1, 3),
        }),
        (3, "AWPV2DirectorPlan", "Director 规划", {
            "round_snapshot": (2, 0),
        }),

        # D1
        (10, "AWPV2HistoryRecallTrigger", "D1 触发", {
            "snapshot": (2, 0),
            "director_plan": (3, 0),
        }),
        (11, "AWPV2HistoryRecallAgent", "D1 历史回查", {
            "snapshot": (2, 0),
            "trigger_result": (10, 0),
        }),
        (12, "AWPV2HistoryRecallResult", "D1 结果", {
            "history_recall_result": (11, 0),
        }),

        # D2
        (13, "AWPV2OpportunityTrigger", "D2 触发", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
        }),
        (14, "AWPV2OpportunityAgent", "D2 戏剧机会", {
            "round_snapshot": (2, 0),
            "trigger_result": (13, 0),
        }),
        (15, "AWPV2OpportunityResult", "D2 结果", {
            "opportunity_result": (14, 0),
        }),

        # D3
        (16, "AWPV2WorldLifeTrigger", "D3 触发", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
            "opportunity_result": (15, 0),
        }),
        (17, "AWPV2WorldLifeAgent", "D3 世界活性", {
            "round_snapshot": (2, 0),
            "trigger_result": (16, 0),
        }),
        (18, "AWPV2WorldLifeResult", "D3 结果", {
            "world_life_result": (17, 0),
        }),

        # D4
        (19, "AWPV2EmotionRelationshipTrigger", "D4 触发", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
        }),
        (20, "AWPV2EmotionRelationshipAgent", "D4 情绪关系", {
            "round_snapshot": (2, 0),
            "er_trigger_result": (19, 0),
        }),

        # D5
        (21, "AWPV2ContinuityTrigger", "D5 触发", {
            "round_snapshot": (2, 0),
            "director_plan": (3, 0),
            "history_recall_result": (12, 0),
            "opportunity_result": (15, 0),
        }),
        (22, "AWPV2ContinuityAgent", "D5 连续性", {
            "round_snapshot": (2, 0),
            "trigger_result": (21, 0),
        }),
        (23, "AWPV2ContinuityResult", "D5 结果", {
            "continuity_result": (22, 0),
        }),

        # D6
        (30, "AWPV2MemoryCuratorAgent", "D6 记忆治理", {
            "quality_decision": (3, 0),
            "turn_record": (3, 0),
            "round_snapshot": (2, 0),
        }),
        (31, "AWPV2MemoryCurationValidator", "D6 验证", {
            "curation_result": (30, 0),
            "curation_request": (30, 0),
        }),
        (32, "AWPV2MemoryCurationRanker", "D6 排序", {
            "curation_result": (31, 0),
        }),

        # Outputs
        (90, "AWPV2TraceDisplay", "【输出】D1 历史回查", {
            "data": (12, 0),
            "label": "D1 History Recall",
        }),
        (91, "AWPV2TraceDisplay", "【输出】D2 戏剧机会", {
            "data": (15, 0),
            "label": "D2 Opportunity",
        }),
        (92, "AWPV2TraceDisplay", "【输出】D3 世界活性", {
            "data": (18, 0),
            "label": "D3 World-Life",
        }),
        (93, "AWPV2TraceDisplay", "【输出】D5 连续性", {
            "data": (23, 0),
            "label": "D5 Continuity",
        }),
        (94, "AWPV2TraceDisplay", "【输出】D6 记忆治理", {
            "data": (32, 0),
            "label": "D6 Memory Curation",
        }),
        (95, "AWPV2TraceDisplay", "【输出】Director 规划", {
            "data": (3, 0),
            "label": "Director Plan",
        }),
        (96, "AWPV2TraceDisplay", "【输出】世界书+历史+记忆", {
            "data": (2, 0),
            "label": "RoundSnapshot",
        }),
    ], {
        "_comment": "子Agent展示: D1-D6 独立链路。用于理解和调试子Agent架构。",
        "_usage": "需要先 bootstrap 会话。修改 session_id 和 player_input 后运行。",
    })

    print("Done.")


if __name__ == "__main__":
    main()
