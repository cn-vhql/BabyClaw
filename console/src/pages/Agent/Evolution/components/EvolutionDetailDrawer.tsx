import { Card, Drawer, Empty, Spinner, Tabs, Tag } from "@agentscope-ai/design";
import { useEffect, useState } from "react";
import { evolutionApi } from "../../../../api/modules/evolution";
import type {
  EvolutionArchive,
  EvolutionRecord,
} from "../../../../api/types/evolution";
import { LazyMarkdown } from "../../../../components/LazyMarkdown";
import { stripFrontmatter } from "../../../../utils/markdown";
import styles from "./EvolutionDetailDrawer.module.less";

interface Props {
  open: boolean;
  record: EvolutionRecord | null;
  onClose: () => void;
}

type NormalizedToolLog = {
  key: string;
  tool: string;
  callId?: string;
  timestamp?: string;
  args?: unknown;
  result?: unknown;
};

type NormalizedStructuredRecord = {
  key: string;
  type: string;
  source?: string;
  timestamp?: string;
  data: unknown;
};

function formatDisplayTime(timestamp?: string): string {
  if (!timestamp) return "时间未知";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return parsed.toLocaleString();
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function renderCenteredEmpty(description: string) {
  return (
    <div className={styles.emptyPanel}>
      <Empty description={description} />
    </div>
  );
}

function MarkdownPreview({ content }: { content: string }) {
  return (
    <div className={styles.markdownPanel}>
      <LazyMarkdown
        content={stripFrontmatter(content || "")}
        className={styles.markdownContent}
      />
    </div>
  );
}

function normalizeToolLogs(archive: EvolutionArchive | null): NormalizedToolLog[] {
  if (!archive || !Array.isArray(archive.tool_execution_log)) return [];

  return archive.tool_execution_log.map((entry, index) => {
    if (entry && typeof entry === "object") {
      return {
        key: `${entry.call_id || entry.tool || "tool"}-${index}`,
        tool: entry.tool || `工具调用 ${index + 1}`,
        callId: entry.call_id,
        timestamp: entry.timestamp,
        args: entry.args,
        result: entry.result,
      };
    }

    return {
      key: `tool-${index}`,
      tool: `工具调用 ${index + 1}`,
      result: entry,
    };
  });
}

function normalizeStructuredRecords(
  archive: EvolutionArchive | null,
): NormalizedStructuredRecord[] {
  if (!archive || !Array.isArray(archive.structured_records)) return [];

  return archive.structured_records
    .filter((entry) => entry && typeof entry === "object")
    .map((entry, index) => ({
      key: `structured-${index}`,
      type: entry.type || "record",
      source: entry.source,
      timestamp: entry.timestamp,
      data: entry.data,
    }));
}

export function EvolutionDetailDrawer({ open, record, onClose }: Props) {
  const [archive, setArchive] = useState<EvolutionArchive | null>(null);
  const [detail, setDetail] = useState<EvolutionRecord | null>(null);
  const [activeTab, setActiveTab] = useState("soul");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && record) {
      setArchive(null);
      setDetail(null);
      setActiveTab("soul");
      void loadDetail(record.id);
      return;
    }

    setArchive(null);
    setDetail(null);
    setActiveTab("soul");
  }, [open, record]);

  const loadDetail = async (recordId: string) => {
    setLoading(true);
    try {
      const [nextRecord, nextArchive] = await Promise.all([
        evolutionApi.getRecord(recordId),
        evolutionApi.getArchiveByRecord(recordId).catch(() => null),
      ]);
      setDetail(nextRecord);
      setArchive(nextArchive);
    } catch (error) {
      console.error("Failed to load evolution detail:", error);
      setDetail(null);
      setArchive(null);
    } finally {
      setLoading(false);
    }
  };

  const renderFileDiff = (filename: string) => {
    const before = archive?.before_files?.[filename];
    const after = archive?.after_files?.[filename];
    if (!before && !after) return renderCenteredEmpty("无数据");

    return (
      <div className={styles.fileDiff}>
        <Card title="进化前" size="small" className={styles.detailCard}>
          {before ? (
            <MarkdownPreview content={before} />
          ) : (
            renderCenteredEmpty("无进化前内容")
          )}
        </Card>
        <Card title="进化后" size="small" className={styles.detailCard}>
          {after ? (
            <MarkdownPreview content={after} />
          ) : (
            renderCenteredEmpty("无进化后内容")
          )}
        </Card>
      </div>
    );
  };

  const renderToolsTab = () => {
    if (!detail) return null;
    const toolLogs = normalizeToolLogs(archive);
    const toolsUsed = Array.isArray(detail.tools_used) ? detail.tools_used : [];
    const derivedToolsUsed =
      toolsUsed.length > 0
        ? toolsUsed
        : Array.from(new Set(toolLogs.map((log) => log.tool).filter(Boolean)));
    const toolCallCount = Math.max(detail.tool_calls_count || 0, toolLogs.length);

    return (
      <div className={styles.toolsTab}>
        <Card title="工具使用统计" size="small" className={styles.detailCard}>
          <p>
            调用次数: <Tag color="blue">{toolCallCount}</Tag>
          </p>
          <p>使用的工具:</p>
          <ul>
            {derivedToolsUsed.length > 0 ? (
              derivedToolsUsed.map((tool) => (
                <li key={tool}>
                  <Tag>{tool}</Tag>
                </li>
              ))
            ) : (
              <li className={styles.placeholderText}>暂无工具使用记录</li>
            )}
          </ul>
        </Card>

        {toolLogs.length > 0 ? (
          <Card
            title={`工具调用详情 (${toolLogs.length})`}
            size="small"
            className={styles.detailCard}
          >
            {toolLogs.map((log) => (
              <div key={log.key} className={styles.toolLog}>
                <div className={styles.toolLogHeader}>
                  <strong>{log.tool}</strong>
                  {log.callId ? <Tag>{log.callId}</Tag> : null}
                  <span>{formatDisplayTime(log.timestamp)}</span>
                </div>
                {log.args !== undefined && stringifyValue(log.args) ? (
                  <div className={styles.toolLogSection}>
                    <strong>参数:</strong>
                    <pre className={styles.fileContent}>{stringifyValue(log.args)}</pre>
                  </div>
                ) : null}
                {log.result !== undefined && log.result !== null ? (
                  <div className={styles.toolLogSection}>
                    <strong>结果:</strong>
                    <pre className={styles.fileContent}>{stringifyValue(log.result)}</pre>
                  </div>
                ) : null}
              </div>
            ))}
          </Card>
        ) : (
          <Card title="工具调用详情" size="small" className={styles.detailCard}>
            {renderCenteredEmpty("无工具调用详情")}
          </Card>
        )}
      </div>
    );
  };

  const renderStructuredTab = () => {
    const structuredRecords = normalizeStructuredRecords(archive);
    const evolutionLog = archive?.after_files?.["EVOLUTION.md"];

    if (!evolutionLog && structuredRecords.length === 0) {
      return renderCenteredEmpty("无结构记录");
    }

    return (
      <div className={styles.structuredTab}>
        {evolutionLog ? (
          <Card title="EVOLUTION.md" size="small" className={styles.detailCard}>
            <MarkdownPreview content={evolutionLog} />
          </Card>
        ) : null}
        {structuredRecords.length > 0 ? (
          <Card
            title={`结构记录 (${structuredRecords.length})`}
            size="small"
            className={styles.detailCard}
          >
            {structuredRecords.map((entry) => (
              <div key={entry.key} className={styles.structuredRecord}>
                <div className={styles.recordMeta}>
                  <Tag color="blue">{entry.type}</Tag>
                  {entry.source ? <Tag>{entry.source}</Tag> : null}
                  <span>{formatDisplayTime(entry.timestamp)}</span>
                </div>
                <pre className={styles.fileContent}>{stringifyValue(entry.data)}</pre>
              </div>
            ))}
          </Card>
        ) : null}
      </div>
    );
  };

  const renderOutputTab = () => {
    const output = archive?.full_output || detail?.output_summary || "";
    return (
      <Card title="智能体输出" size="small" className={styles.detailCard}>
        {output ? (
          <pre className={styles.fileContent}>{output}</pre>
        ) : (
          renderCenteredEmpty("无输出")
        )}
      </Card>
    );
  };

  const renderMemoryTab = () => {
    if (!archive?.memory_snapshot) return renderCenteredEmpty("无记忆快照");
    return (
      <Card title="记忆快照" size="small" className={styles.detailCard}>
        <pre className={styles.fileContent}>
          {JSON.stringify(archive.memory_snapshot, null, 2)}
        </pre>
      </Card>
    );
  };

  const renderActiveTab = () => {
    switch (activeTab) {
      case "soul":
        return renderFileDiff("SOUL.md");
      case "profile":
        return renderFileDiff("PROFILE.md");
      case "plan":
        return renderFileDiff("PLAN.md");
      case "tools":
        return renderToolsTab();
      case "structured":
        return renderStructuredTab();
      case "output":
        return renderOutputTab();
      case "memory":
        return renderMemoryTab();
      default:
        return null;
    }
  };

  const tabItems = [
    { key: "soul", label: "Soul" },
    { key: "profile", label: "Profile" },
    { key: "plan", label: "Plan" },
    { key: "tools", label: "工具记录" },
    { key: "structured", label: "结构记录" },
    { key: "output", label: "输出" },
    ...(archive?.memory_snapshot ? [{ key: "memory", label: "记忆" }] : []),
  ];

  return (
    <Drawer
      title={`进化详情 - 第${detail?.generation || record?.generation || "-"}代`}
      onClose={onClose}
      open={open}
      width={860}
    >
      {loading ? (
        <div className={styles.loadingPanel}>
          <Spinner />
        </div>
      ) : (
        <div className={styles.tabsWrapper}>
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
          {renderActiveTab()}
        </div>
      )}
    </Drawer>
  );
}
