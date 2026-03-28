import { useEffect, useRef, useState } from "react";
import {
  Button,
  Popconfirm,
  Table,
  Tag,
  message,
} from "@agentscope-ai/design";
import { evolutionApi } from "../../../api/modules/evolution";
import type {
  EvolutionConfig,
  EvolutionRecord,
} from "../../../api/types/evolution";
import { useAgentStore } from "../../../stores/agentStore";
import { EvolutionDetailDrawer } from "./components/EvolutionDetailDrawer";
import { EvolutionSettingsModal } from "./components/EvolutionSettingsModal";
import styles from "./index.module.less";

type EvolutionApiError = Error & {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

function EvolutionPage() {
  const { selectedAgent } = useAgentStore();
  const [records, setRecords] = useState<EvolutionRecord[]>([]);
  const [config, setConfig] = useState<EvolutionConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<EvolutionRecord | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pageVisible, setPageVisible] = useState(
    typeof document === "undefined" ? true : !document.hidden,
  );
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const hasRunningRecord = records.some((record) => record.status === "running");

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  };

  const loadConfig = async () => {
    if (!selectedAgent) return;
    try {
      const nextConfig = await evolutionApi.getConfig();
      setConfig(nextConfig);
    } catch {
      message.error("加载进化配置失败");
    }
  };

  const loadRecords = async () => {
    if (!selectedAgent) return;
    setLoading(true);
    try {
      const nextRecords = await evolutionApi.listRecords(50);
      setRecords(nextRecords || []);
    } catch {
      message.error("加载进化记录失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadConfig();
    void loadRecords();
    return () => stopPolling();
  }, [selectedAgent]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setPageVisible(!document.hidden);
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (pageVisible && hasRunningRecord) {
      if (!pollingRef.current) {
        pollingRef.current = setInterval(() => {
          void loadRecords();
        }, 5000);
      }
      return;
    }
    stopPolling();
  }, [hasRunningRecord, pageVisible, selectedAgent]);

  const handleRunEvolution = async () => {
    try {
      setActionLoading(true);
      await evolutionApi.runEvolution({ trigger_type: "manual" });
      message.success("进化任务已启动");
      await loadRecords();
    } catch (error) {
      const evolutionError = error as EvolutionApiError;
      message.error(evolutionError.response?.data?.detail || "启动进化失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelRecord = async (record: EvolutionRecord) => {
    try {
      setActionLoading(true);
      await evolutionApi.cancelRecord(record.id);
      message.success("进化任务已取消");
      await loadRecords();
    } catch (error) {
      const evolutionError = error as EvolutionApiError;
      message.error(evolutionError.response?.data?.detail || "取消失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteRecord = async (record: EvolutionRecord) => {
    try {
      setActionLoading(true);
      await evolutionApi.deleteRecord(record.id);
      message.success("记录已删除");
      await loadRecords();
    } catch (error) {
      const evolutionError = error as EvolutionApiError;
      message.error(evolutionError.response?.data?.detail || "删除失败");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRollbackRecord = async (record: EvolutionRecord) => {
    try {
      setActionLoading(true);
      await evolutionApi.rollbackRecord(record.id);
      message.success("已回退到上一成功版本");
      await loadRecords();
      if (selectedRecord?.id === record.id) {
        setSelectedRecord({ ...record, status: "reverted", is_active: false });
      }
    } catch (error) {
      const evolutionError = error as EvolutionApiError;
      message.error(evolutionError.response?.data?.detail || "回退失败");
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      running: { color: "blue", text: "运行中" },
      success: { color: "green", text: "成功" },
      failed: { color: "red", text: "失败" },
      cancelled: { color: "orange", text: "已取消" },
      reverted: { color: "default", text: "已作废" },
    };
    const { color, text } = statusMap[status] || { color: "default", text: status };
    return <Tag color={color}>{text}</Tag>;
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      const hours = String(date.getHours()).padStart(2, "0");
      const minutes = String(date.getMinutes()).padStart(2, "0");
      const seconds = String(date.getSeconds()).padStart(2, "0");
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch {
      return timestamp;
    }
  };

  const columns = [
    {
      title: "代数",
      dataIndex: "generation",
      width: 140,
      render: (_: number, record: EvolutionRecord) => (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>第 {record.generation} 代</span>
          {record.is_active ? <Tag color="gold">当前生效</Tag> : null}
        </div>
      ),
    },
    {
      title: "时间",
      dataIndex: "timestamp",
      width: 180,
      render: (timestamp: string) => formatTimestamp(timestamp),
    },
    {
      title: "触发方式",
      dataIndex: "trigger_type",
      width: 100,
      render: (type: string) => {
        const typeMap: Record<string, string> = {
          manual: "手动",
          cron: "定时",
          auto: "自动",
        };
        return typeMap[type] || type;
      },
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: getStatusTag,
    },
    { title: "工具调用", dataIndex: "tool_calls_count", width: 100 },
    {
      title: "摘要",
      dataIndex: "output_summary",
      ellipsis: true,
    },
    {
      title: "操作",
      key: "actions",
      className: "copaw-table-actions-cell",
      onHeaderCell: () => ({ className: "copaw-table-actions-cell" }),
      width: 220,
      render: (_: unknown, record: EvolutionRecord) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button type="link" size="small" onClick={() => {
            setSelectedRecord(record);
            setDrawerOpen(true);
          }}>
            查看详情
          </Button>
          {record.status === "running" ? (
            <Popconfirm
              title="确认取消"
              description="确定要取消这条运行中的进化任务吗？"
              onConfirm={() => handleCancelRecord(record)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" size="small" danger>
                取消
              </Button>
            </Popconfirm>
          ) : null}
          {record.status === "failed" || record.status === "cancelled" ? (
            <Popconfirm
              title="确认删除"
              description="确定要删除这条记录吗？"
              onConfirm={() => handleDeleteRecord(record)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" size="small" danger>
                删除
              </Button>
            </Popconfirm>
          ) : null}
          {record.status === "success" && record.is_active ? (
            <Popconfirm
              title="确认作废并回退"
              description="确定要作废当前生效版本，并回退到上一成功版本吗？"
              onConfirm={() => handleRollbackRecord(record)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" size="small">
                作废并回退
              </Button>
            </Popconfirm>
          ) : null}
        </div>
      ),
    },
  ];

  const runDisabled = actionLoading || hasRunningRecord || config?.enabled === false;

  return (
    <div className={styles.evolutionPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>数字生命进化</h1>
          <p className={styles.description}>
            智能体通过自主探索和学习，不断更新自我认知，成长为数字生命
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={() => setSettingsOpen(true)}>设置</Button>
          <Button
            type="primary"
            onClick={handleRunEvolution}
            disabled={runDisabled}
          >
            {hasRunningRecord ? "进化中..." : "立即进化"}
          </Button>
        </div>
      </div>

      <Table
        columns={columns}
        dataSource={records}
        loading={loading || actionLoading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />

      <EvolutionDetailDrawer
        open={drawerOpen}
        record={selectedRecord}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedRecord(null);
        }}
      />

      <EvolutionSettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onConfigSaved={() => {
          void loadConfig();
          void loadRecords();
        }}
      />
    </div>
  );
}

export default EvolutionPage;
