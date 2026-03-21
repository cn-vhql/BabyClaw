import { useState, useMemo } from "react";
import { Table, Card, Button, Switch, Empty, Tag } from "@agentscope-ai/design";
import { useTools } from "./useTools";
import { useTranslation } from "react-i18next";
import type { ToolInfo } from "../../../api/modules/tools";
import styles from "./index.module.less";

export default function ToolsPage() {
  const { t } = useTranslation();
  const { tools, loading, batchLoading, toggleEnabled, enableAll, disableAll } =
    useTools();

  const handleToggle = (tool: ToolInfo) => {
    toggleEnabled(tool);
  };

  const hasDisabledTools = useMemo(
    () => tools.some((tool) => !tool.enabled),
    [tools],
  );
  const hasEnabledTools = useMemo(
    () => tools.some((tool) => tool.enabled),
    [tools],
  );

  const columns = [
    {
      title: t("tools.name"),
      dataIndex: "name",
      key: "name",
      ellipsis: true,
    },
    {
      title: t("tools.type"),
      dataIndex: "isBuiltin",
      key: "type",
      width: 100,
      render: (_: unknown, record: ToolInfo) => (
        <Tag color={record.isBuiltin ? "geekblue" : "green"}>
          {record.isBuiltin ? t("tools.builtin") : t("tools.custom")}
        </Tag>
      ),
    },
    {
      title: t("tools.status"),
      dataIndex: "enabled",
      key: "status",
      width: 100,
      render: (enabled: boolean, record: ToolInfo) => (
        <Switch
          size="small"
          checked={enabled}
          onChange={() => handleToggle(record)}
        />
      ),
    },
    {
      title: t("tools.actions"),
      key: "actions",
      width: 120,
      render: (_: unknown, record: ToolInfo) => (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Button
            type="link"
            size="small"
            onClick={() => handleToggle(record)}
          >
            {record.enabled ? t("common.disable") : t("common.enable")}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className={styles.toolsPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{t("tools.title")}</h1>
          <p className={styles.description}>{t("tools.description")}</p>
        </div>
        <div className={styles.actionTabs}>
          <Button
            className={`${styles.actionTab} ${
              !hasDisabledTools ? styles.disabledTab : ""
            }`}
            onClick={enableAll}
            disabled={batchLoading || loading || !hasDisabledTools}
            type="text"
            size="small"
          >
            {t("tools.enableAll")}
          </Button>
          <Button
            className={`${styles.actionTab} ${
              !hasEnabledTools ? styles.disabledTab : ""
            }`}
            onClick={disableAll}
            disabled={batchLoading || loading || !hasEnabledTools}
            type="text"
            size="small"
          >
            {t("tools.disableAll")}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className={styles.loading}>
          <p>{t("common.loading")}</p>
        </div>
      ) : tools.length === 0 ? (
        <Empty description={t("tools.emptyState")} />
      ) : (
        <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
          <Table
            columns={columns}
            dataSource={tools}
            rowKey="name"
            pagination={{
              pageSize: 10,
              showSizeChanger: false,
              showTotal: (total) => t("tools.totalItems", { count: total }),
            }}
            size="small"
          />
        </Card>
      )}
    </div>
  );
}
