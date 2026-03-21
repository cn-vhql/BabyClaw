import { Drawer, Tabs, Card, Spinner, Empty, Tag } from "@agentscope-ai/design";
import { useState, useEffect } from "react";
import { evolutionApi } from "../../../../api/modules/evolution";
import type { EvolutionRecord, EvolutionArchive } from "../../../../api/types/evolution";
import styles from "./EvolutionDetailDrawer.module.less";

interface Props {
  open: boolean;
  record: EvolutionRecord | null;
  onClose: () => void;
}

export function EvolutionDetailDrawer({ open, record, onClose }: Props) {
  const [archive, setArchive] = useState<EvolutionArchive | null>(null);
  const [activeTab, setActiveTab] = useState("soul");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && record) {
      loadArchive();
    }
  }, [open, record]);

  const loadArchive = async () => {
    if (!record) return;
    setLoading(true);
    try {
      const archive = await evolutionApi.getArchive(record.id);
      setArchive(archive);
    } catch (error) {
      console.error("Failed to load archive:", error);
    } finally {
      setLoading(false);
    }
  };

  const renderFileDiff = (before: string | undefined, after: string | undefined) => {
    if (!before && !after) return <Empty description="无数据" />;
    return (
      <div className={styles.fileDiff}>
        <Card title="进化前" size="small" style={{ marginBottom: 16 }}>
          <pre className={styles.fileContent}>{before || "无"}</pre>
        </Card>
        <Card title="进化后" size="small">
          <pre className={styles.fileContent}>{after || "无"}</pre>
        </Card>
      </div>
    );
  };

  const renderSoulTab = () => {
    if (!record) return null;
    return renderFileDiff(record.soul_before, record.soul_after);
  };

  const renderProfileTab = () => {
    if (!record) return null;
    return renderFileDiff(record.profile_before, record.profile_after);
  };

  const renderPlanTab = () => {
    if (!record) return null;
    return renderFileDiff(record.plan_before, record.plan_after);
  };

  const renderToolsTab = () => {
    if (!record) return null;
    return (
      <div className={styles.toolsTab}>
        <Card title="工具使用统计" size="small">
          <p>
            调用次数: <Tag color="blue">{record.tool_calls_count}</Tag>
          </p>
          <p>使用的工具:</p>
          <ul>
            {record.tools_used.length > 0 ? (
              record.tools_used.map((tool) => (
                <li key={tool}>
                  <Tag>{tool}</Tag>
                </li>
              ))
            ) : (
              <li style={{ color: "#999" }}>暂无工具使用记录</li>
            )}
          </ul>
        </Card>

        {archive && archive.tool_execution_log.length > 0 && (
          <Card title="工具调用详情" size="small" style={{ marginTop: 16 }}>
            {archive.tool_execution_log.map((log, index) => (
              <div key={index} className={styles.toolLog}>
                <p>
                  <strong>{log.tool}</strong> - {new Date(log.timestamp).toLocaleString()}
                </p>

                {log.args && Object.keys(log.args).length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <strong>参数:</strong>
                    <pre className={styles.fileContent}>
                      {JSON.stringify(log.args, null, 2)}
                    </pre>
                  </div>
                )}

                {log.result !== undefined && log.result !== null && (
                  <div style={{ marginTop: 8 }}>
                    <strong>结果:</strong>
                    <pre className={styles.fileContent}>
                      {typeof log.result === "string"
                        ? log.result
                        : JSON.stringify(log.result, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </Card>
        )}
      </div>
    );
  };

  const renderOutputTab = () => {
    const output = archive?.full_output || record?.output_summary || "";
    const outputLength = output?.length || 0;

    return (
      <Card
        title={`智能体输出 ${outputLength > 0 ? `(${outputLength} 字符)` : ""}`}
        size="small"
      >
        {output ? (
          <pre className={styles.fileContent}>{output}</pre>
        ) : (
          <Empty description="无输出" />
        )}
      </Card>
    );
  };

  const renderMemoryTab = () => {
    if (!archive) return <Empty description="无记忆快照" />;
    return (
      <Card title="记忆快照" size="small">
        <pre className={styles.fileContent}>
          {JSON.stringify(archive.memory_snapshot, null, 2)}
        </pre>
      </Card>
    );
  };

  const tabItems = [
    { key: "soul", label: "Soul", children: renderSoulTab() },
    { key: "profile", label: "Profile", children: renderProfileTab() },
    { key: "plan", label: "Plan", children: renderPlanTab() },
    { key: "tools", label: "工具记录", children: renderToolsTab() },
    { key: "output", label: "输出", children: renderOutputTab() },
    { key: "memory", label: "记忆", children: renderMemoryTab() },
  ];

  return (
    <Drawer
      title={`进化详情 - 第${record?.generation}代`}
      onClose={onClose}
      open={open}
      width={800}
    >
      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spinner size="large" />
        </div>
      ) : (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
      )}
    </Drawer>
  );
}
