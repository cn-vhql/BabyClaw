import { useState, useEffect, useRef } from "react";
import {
  Button,
  Card,
  Table,
  message,
  Tag,
  Modal,
  Popconfirm,
} from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import { useAgentStore } from "../../../stores/agentStore";
import { evolutionApi } from "../../../api/modules/evolution";
import type { EvolutionRecord } from "../../../api/types/evolution";
import { EvolutionDetailDrawer } from "./components/EvolutionDetailDrawer";
import { EvolutionSettingsModal } from "./components/EvolutionSettingsModal";
import styles from "./index.module.less";

function EvolutionPage() {
  const { t } = useTranslation();
  const { selectedAgent } = useAgentStore();
  const [records, setRecords] = useState<EvolutionRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [evolving, setEvolving] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<EvolutionRecord | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    loadRecords();
    return () => {
      // Cleanup polling on unmount
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [selectedAgent]);

  const loadRecords = async () => {
    if (!selectedAgent) return;
    setLoading(true);
    try {
      const records = await evolutionApi.listRecords(50);
      setRecords(records || []);

      // Check if there's a running record
      const runningRecord = records?.find(r => r.status === "running");
      if (runningRecord && !pollingRef.current) {
        startPolling();
      } else if (!runningRecord && pollingRef.current) {
        stopPolling();
      }
    } catch (error) {
      message.error("加载进化记录失败");
    } finally {
      setLoading(false);
    }
  };

  const startPolling = () => {
    if (pollingRef.current) return;
    setEvolving(true);
    pollingRef.current = setInterval(() => {
      loadRecords();
    }, 3000); // Poll every 3 seconds
  };

  const stopPolling = () => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setEvolving(false);
  };

  const handleRunEvolution = async () => {
    try {
      setEvolving(true);
      await evolutionApi.runEvolution({ trigger_type: "manual" });
      message.success("进化任务已启动");
      startPolling();
      loadRecords();
    } catch (error) {
      message.error("启动进化失败");
      setEvolving(false);
    }
  };

  const handleViewDetail = (record: EvolutionRecord) => {
    setSelectedRecord(record);
    setDrawerOpen(true);
  };

  const handleDeleteRecord = async (record: EvolutionRecord) => {
    try {
      await evolutionApi.deleteRecord(record.id);
      message.success("记录已删除");
      loadRecords();
    } catch (error: any) {
      const errorMsg = error?.response?.data?.detail || "删除失败";
      message.error(errorMsg);
    }
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      running: { color: "blue", text: "运行中" },
      success: { color: "green", text: "成功" },
      failed: { color: "red", text: "失败" },
      cancelled: { color: "orange", text: "已取消" },
    };
    const { color, text } = statusMap[status] || { color: "default", text: status };
    return <Tag color={color}>{text}</Tag>;
  };

  const columns = [
    { title: "代数", dataIndex: "generation", width: 80 },
    { title: "时间", dataIndex: "timestamp", width: 180 },
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
      width: 150,
      render: (_: unknown, record: EvolutionRecord) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="link"
            size="small"
            onClick={() => handleViewDetail(record)}
          >
            查看详情
          </Button>
          {record.status === "failed" && (
            <Popconfirm
              title="确认删除"
              description="确定要删除这条失败的进化记录吗？"
              onConfirm={() => handleDeleteRecord(record)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="link" size="small" danger>
                删除
              </Button>
            </Popconfirm>
          )}
        </div>
      ),
    },
  ];

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
            disabled={evolving}
            loading={evolving}
          >
            {evolving ? "进化中..." : "立即进化"}
          </Button>
        </div>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={records}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>

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
          loadRecords();
        }}
      />
    </div>
  );
}

export default EvolutionPage;
