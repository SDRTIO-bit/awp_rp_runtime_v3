import { useEffect, useState } from "react";
import { Button, Collapse, Modal, Select, Typography } from "antd";
import { FolderOpenOutlined } from "@ant-design/icons";
import { getWriterPreset, listWriterPresets } from "../api/client";

const { Paragraph, Text } = Typography;

export default function PresetViewer() {
  const [presets, setPresets] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [content, setContent] = useState("");
  const [path, setPath] = useState("");

  useEffect(() => {
    listWriterPresets()
      .then(setPresets)
      .catch(() => setPresets([]));
  }, []);

  useEffect(() => {
    if (!selected) {
      setContent("");
      setPath("");
      return;
    }
    getWriterPreset(selected)
      .then((preset) => {
        setContent(preset.content);
        setPath(preset.path);
      })
      .catch(() => {
        setContent("");
        setPath("");
      });
  }, [selected]);

  return (
    <Collapse
      ghost
      items={[
        {
          key: "writer-presets",
          label: "Writer presets",
          children: (
            <>
              <Select
                options={presets.map((preset) => ({ value: preset, label: preset }))}
                placeholder="Select a preset"
                style={{ width: "100%" }}
                value={selected || undefined}
                onChange={setSelected}
              />
              {selected && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Path: {path}
                  </Text>
                  <Paragraph
                    style={{
                      marginTop: 8,
                      whiteSpace: "pre-wrap",
                      maxHeight: 220,
                      overflow: "auto",
                      background: "#fff",
                      border: "1px solid #f0f0f0",
                      padding: 8,
                      borderRadius: 6,
                    }}
                  >
                    {content}
                  </Paragraph>
                  <Button
                    size="small"
                    icon={<FolderOpenOutlined />}
                    onClick={() => {
                      Modal.info({
                        title: "Edit preset",
                        content: `Open this file from the local filesystem: ${path}`,
                      });
                    }}
                  >
                    Locate file
                  </Button>
                </div>
              )}
            </>
          ),
        },
      ]}
    />
  );
}
