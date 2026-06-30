import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import { Card, Collapse, Drawer, Space, Tag, Typography, message } from "antd";
import { sendTurnStream, StepPayload, StreamEvent } from "../api/client";

const { Paragraph, Text } = Typography;

const STEP_LABELS: Record<string, string> = {
  round_snapshot: "回合快照",
  director: "总控规划",
  director_delegation: "总控委派",
  sub_agents: "子代理分析",
  writer: "写作",
  quality_gate: "质量门",
  turn_evolution_curator: "演进策展",
  state_commit: "状态提交",
  memory_curator: "记忆治理",
};

type StepStatus = "pending" | "done" | "failed";

interface StepState {
  name: string;
  label: string;
  status: StepStatus;
  payload?: StepPayload;
  duration_ms?: number;
  writerOutput?: string;
}

interface PipelineStreamDrawerProps {
  open: boolean;
  onClose: () => void;
  sessionId: string;
  playerInput: string;
  streamRunId: number;
  onComplete: () => void;
  onRunningChange?: (running: boolean) => void;
}

function initialSteps(names: string[]): StepState[] {
  return names.map((name) => ({
    name,
    label: STEP_LABELS[name] || name,
    status: "pending",
  }));
}

function valueText(value: unknown): string {
  if (value === undefined || value === null || value === "") return "-";
  if (typeof value === "number") return Number.isFinite(value) ? String(value) : "-";
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function statusIcon(status: StepStatus) {
  if (status === "done") return <CheckCircleOutlined style={{ color: "#52c41a" }} />;
  if (status === "failed") return <CloseCircleOutlined style={{ color: "#ff4d4f" }} />;
  return <ClockCircleOutlined style={{ color: "#8c8c8c" }} />;
}

function verdictText(verdict: unknown): string {
  if (verdict === "pass") return "通过";
  if (verdict === "fail") return "拒绝";
  return valueText(verdict);
}

function finalizeFailedSteps(steps: StepState[]): StepState[] {
  if (steps.some((step) => step.status === "failed")) return steps;

  const next = [...steps];
  for (let i = next.length - 1; i >= 0; i -= 1) {
    if (next[i].status === "done") {
      next[i] = { ...next[i], status: "failed" };
      return next;
    }
  }
  if (next.length > 0) next[0] = { ...next[0], status: "failed" };
  return next;
}

function formatStreamError(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error || "");
  if (text.includes("No tool_call or valid JSON in response")) {
    return "模型没有返回可用的工具调用或 JSON";
  }
  if (text.includes("EMPTY_RESPONSE")) {
    return "模型返回了空响应";
  }
  if (text.includes("Streaming response body unavailable")) {
    return "流式响应正文不可用";
  }
  return text || "发送失败";
}

function renderStepBody(step: StepState) {
  const payload = step.payload || {};
  if (step.status === "pending" && !step.payload) {
    return <Text type="secondary">等待执行</Text>;
  }

  switch (step.name) {
    case "round_snapshot":
      return (
        <Text>
          召回 L1:{valueText(payload.l1_turn_ids_recalled_count)} L2:
          {valueText(payload.l2_memory_ids_recalled_count)} L3:
          {valueText(payload.l3_memory_ids_recalled_count)} | 世界书：
          {valueText(payload.worldbook_activated_count)}
        </Text>
      );
    case "director":
      return (
        <Space direction="vertical" size={2}>
          <Text>
            {valueText(payload.provider_type)} / {valueText(payload.model)}
          </Text>
          <Text type="secondary">计划：{valueText(payload.plan_ref).slice(0, 48)}</Text>
          {payload.call_success === false && <Tag color="red">{valueText(payload.failure_code)}</Tag>}
        </Space>
      );
    case "director_delegation":
      return (
        <Space direction="vertical" size={4}>
          <Text type="secondary">{valueText(payload.source)}</Text>
          <Space wrap>
            {Array.isArray(payload.requested_agents) && payload.requested_agents.length > 0
              ? payload.requested_agents.map((agent) => <Tag key={String(agent)}>{String(agent)}</Tag>)
              : <Tag>无</Tag>}
          </Space>
        </Space>
      );
    case "sub_agents": {
      const dispositions = (payload.agent_dispositions || {}) as Record<string, unknown>;
      const items = Object.entries(dispositions).map(([role, summary]) => ({
        key: role,
        label: role,
        children: <Paragraph style={{ marginBottom: 0 }}>{valueText(summary)}</Paragraph>,
      }));
      return items.length > 0 ? (
        <Collapse size="small" ghost items={items} />
      ) : (
        <Text type="secondary">没有子代理</Text>
      );
    }
    case "writer":
      return step.writerOutput ? (
        <Paragraph style={{ maxHeight: 200, overflow: "auto", whiteSpace: "pre-wrap", marginBottom: 0 }}>
          {step.writerOutput}
        </Paragraph>
      ) : (
        <Text type="secondary">正在写作...（{valueText(payload.text_length)} 字）</Text>
      );
    case "quality_gate":
      return (
        <Space direction="vertical" size={4}>
          <Space>
            <Tag color={payload.verdict === "pass" ? "green" : "red"}>
              {verdictText(payload.verdict)}
            </Tag>
            <Text>评分 {valueText(payload.overall_score)}</Text>
          </Space>
          {Array.isArray(payload.blocking_reasons) && payload.blocking_reasons.length > 0 && (
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              {payload.blocking_reasons.join("; ")}
            </Paragraph>
          )}
        </Space>
      );
    case "turn_evolution_curator":
      return (
        <Text>
          状态 {valueText(payload.proposed_state_changes_count)} | 活跃{" "}
          {valueText(payload.memory_candidates_active_count)} | RAG{" "}
          {valueText(payload.memory_candidates_rag_count)} | 置信度{" "}
          {valueText(payload.curator_confidence)}
        </Text>
      );
    case "state_commit":
      return (
        <Text>
          {valueText(payload.commit_status)} | 修订 {valueText(payload.revision_before)}
          {" -> "}
          {valueText(payload.revision_after)}
        </Text>
      );
    case "memory_curator":
      return (
        <Space direction="vertical" size={2}>
          <Text>{valueText(payload.curation_status)}</Text>
          <Text type="secondary">{valueText(payload.curation_reason)}</Text>
          <Text type="secondary">
            提交 {valueText(payload.commit_ids_count)} | 活跃{" "}
            {valueText(payload.active_committed_count)} | RAG{" "}
            {valueText(payload.rag_committed_count)}
          </Text>
        </Space>
      );
    default:
      return <Paragraph style={{ marginBottom: 0 }}>{JSON.stringify(payload)}</Paragraph>;
  }
}

export default function PipelineStreamDrawer({
  open,
  onClose,
  sessionId,
  playerInput,
  streamRunId,
  onComplete,
  onRunningChange,
}: PipelineStreamDrawerProps) {
  const defaultStepNames = useMemo(() => Object.keys(STEP_LABELS), []);
  const [steps, setSteps] = useState<StepState[]>(() => initialSteps(defaultStepNames));
  const [running, setRunning] = useState(false);
  const startedRunRef = useRef<number | null>(null);

  useEffect(() => {
    if (!open || !sessionId || !playerInput || startedRunRef.current === streamRunId) return;
    startedRunRef.current = streamRunId;
    setSteps(initialSteps(defaultStepNames));
    setRunning(true);
    onRunningChange?.(true);
    const controller = new AbortController();

    const handleEvent = (event: StreamEvent) => {
      if (event.type === "started") {
        setSteps(initialSteps(event.steps));
        return;
      }
      if (event.type === "step") {
        setSteps((current) =>
          current.map((step) =>
            step.name === event.step
              ? {
                  ...step,
                  status: event.payload.call_success === false ? "failed" : "done",
                  payload: event.payload,
                  duration_ms: event.duration_ms,
                }
              : step,
          ),
        );
        return;
      }
      if (event.type === "writer_text") {
        setSteps((current) =>
          current.map((step) =>
            step.name === "writer" ? { ...step, writerOutput: event.writer_output } : step,
          ),
        );
        return;
      }
      if (event.type === "done") {
        setRunning(false);
        onRunningChange?.(false);
        if (event.success) {
          onComplete();
        } else {
          setSteps(finalizeFailedSteps);
          message.error(formatStreamError(event.error));
        }
      }
    };

    sendTurnStream(sessionId, playerInput, handleEvent, controller.signal).catch((error) => {
      if (controller.signal.aborted) return;
      setRunning(false);
      onRunningChange?.(false);
      setSteps(finalizeFailedSteps);
      message.error(formatStreamError(error));
    });

    return () => {
      controller.abort();
      onRunningChange?.(false);
    };
  }, [defaultStepNames, onComplete, onRunningChange, open, playerInput, sessionId, streamRunId]);

  return (
    <Drawer
      title="流程"
      placement="left"
      width="min(420px, 100vw)"
      open={open}
      onClose={onClose}
      mask={false}
      extra={running ? <Tag color="processing">运行中</Tag> : <Tag>空闲</Tag>}
    >
      <Space direction="vertical" size={10} style={{ width: "100%" }}>
        {steps.map((step) => (
          <Card
            key={step.name}
            size="small"
            title={
              <Space>
                {statusIcon(step.status)}
                <Text strong>{step.label}</Text>
              </Space>
            }
            extra={
              step.duration_ms !== undefined ? (
                <Text type="secondary">{step.duration_ms}ms</Text>
              ) : null
            }
            styles={{ body: { fontSize: 13 } }}
          >
            {renderStepBody(step)}
          </Card>
        ))}
      </Space>
    </Drawer>
  );
}
