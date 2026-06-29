import { useEffect, useMemo, useState } from "react";
import { Collapse, Radio, Select, Space, Typography } from "antd";
import { listWorkflows, WorkflowInfo } from "../api/client";

const { Text } = Typography;

interface WorkflowSelectorProps {
  action: "turn" | "first_turn" | "continue";
  mode: string;
  workflow: string;
  onModeChange: (mode: string) => void;
  onWorkflowChange: (workflow: string) => void;
}

const actionLabels: Record<WorkflowSelectorProps["action"], string> = {
  turn: "Player turn",
  first_turn: "First turn",
  continue: "Continue",
};

export default function WorkflowSelector({
  action,
  mode,
  workflow,
  onModeChange,
  onWorkflowChange,
}: WorkflowSelectorProps) {
  const [workflows, setWorkflows] = useState<WorkflowInfo[]>([]);

  useEffect(() => {
    listWorkflows()
      .then(setWorkflows)
      .catch(() => setWorkflows([]));
  }, []);

  const workflowOptions = useMemo(
    () =>
      workflows.map((item) => ({
        value: item.name,
        label: `${item.name} (${item.node_count} nodes)`,
      })),
    [workflows],
  );

  return (
    <Collapse
      ghost
      items={[
        {
          key: "execution",
          label: `Execution mode and workflow (${actionLabels[action]})`,
          children: (
            <Space direction="vertical" size={12} style={{ width: "100%" }}>
              <Radio.Group value={mode} onChange={(event) => onModeChange(event.target.value)}>
                <Radio.Button value="hybrid">Workflow</Radio.Button>
                <Radio.Button value="python">Python direct</Radio.Button>
              </Radio.Group>
              <div>
                <Text type="secondary">Workflow</Text>
                <Select
                  allowClear
                  options={workflowOptions}
                  placeholder="Default workflow"
                  style={{ width: "100%", marginTop: 4 }}
                  value={workflow || undefined}
                  onChange={(value) => onWorkflowChange(value || "")}
                />
              </div>
            </Space>
          ),
        },
      ]}
    />
  );
}
