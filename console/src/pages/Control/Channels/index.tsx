import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import api from "../../../api";
import {
  Form,
  message,
  Table,
  Card,
  Tag,
  Switch,
  Button,
} from "@agentscope-ai/design";
import {
  ChannelDrawer,
  useChannels,
  getChannelLabel,
  type ChannelKey,
} from "./components";
import styles from "./index.module.less";

type FilterType = "all" | "builtin" | "custom";

function ChannelsPage() {
  const { t } = useTranslation();
  const { channels, orderedKeys, isBuiltin, loading, fetchChannels } =
    useChannels();
  const [filter, setFilter] = useState<FilterType>("all");
  const [saving, setSaving] = useState(false);
  const [activeKey, setActiveKey] = useState<ChannelKey | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [form] = Form.useForm<any>();

  // Convert cards to table data
  const tableData = useMemo(() => {
    const data: {
      key: ChannelKey;
      config: Record<string, unknown>;
      label: string;
      isBuiltin: boolean;
    }[] = [];

    orderedKeys.forEach((key) => {
      const config = channels[key] || { enabled: false, bot_prefix: "" };
      const builtin = isBuiltin(key);
      if (filter === "builtin" && !builtin) return;
      if (filter === "custom" && builtin) return;

      data.push({
        key,
        config,
        label: getChannelLabel(key),
        isBuiltin: builtin,
      });
    });

    return data;
  }, [channels, orderedKeys, filter, isBuiltin]);

  const handleEdit = (key: ChannelKey) => {
    setActiveKey(key);
    const channelConfig = channels[key] || { enabled: false, bot_prefix: "" };
    form.setFieldsValue({
      ...channelConfig,
      filter_tool_messages: !channelConfig.filter_tool_messages,
      filter_thinking: !channelConfig.filter_thinking,
    });
    setDrawerOpen(true);
  };

  const handleToggleEnabled = async (key: ChannelKey) => {
    const channelConfig = channels[key] || { enabled: false };
    const updatedChannel: Record<string, unknown> = {
      ...channelConfig,
      enabled: !channelConfig.enabled,
    };

    try {
      await api.updateChannelConfig(
        key,
        updatedChannel as unknown as Parameters<
          typeof api.updateChannelConfig
        >[1],
      );
      await fetchChannels();
      message.success(t("channels.configSaved"));
    } catch (error) {
      console.error("❌ Failed to toggle channel:", error);
      message.error(t("channels.configFailed"));
    }
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setActiveKey(null);
  };

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!activeKey) return;

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { isBuiltin: _isBuiltin, ...savedConfig } = channels[activeKey] || {};
    const updatedChannel: Record<string, unknown> = {
      ...savedConfig,
      ...values,
      filter_tool_messages: !values.filter_tool_messages,
      filter_thinking: !values.filter_thinking,
    };

    setSaving(true);
    try {
      await api.updateChannelConfig(
        activeKey,
        updatedChannel as unknown as Parameters<
          typeof api.updateChannelConfig
        >[1],
      );
      await fetchChannels();

      setDrawerOpen(false);
      message.success(t("channels.configSaved"));
    } catch (error) {
      console.error("❌ Failed to update channel config:", error);
      message.error(t("channels.configFailed"));
    } finally {
      setSaving(false);
    }
  };

  const activeLabel = activeKey ? getChannelLabel(activeKey) : "";

  const columns = [
    {
      title: t("channels.name"),
      dataIndex: "label",
      key: "label",
      width: 150,
    },
    {
      title: t("channels.type"),
      dataIndex: "isBuiltin",
      key: "isBuiltin",
      width: 100,
      render: (builtin: boolean) => (
        <Tag color={builtin ? "geekblue" : "green"}>
          {builtin ? t("channels.builtin") : t("channels.custom")}
        </Tag>
      ),
    },
    {
      title: t("channels.status"),
      dataIndex: "config",
      key: "status",
      width: 100,
      render: (config: Record<string, unknown>, record: any) => (
        <Switch
          size="small"
          checked={config.enabled as boolean}
          onChange={() => handleToggleEnabled(record.key)}
        />
      ),
    },
    {
      title: t("channels.botPrefix"),
      dataIndex: "config",
      key: "botPrefix",
      ellipsis: true,
      render: (config: Record<string, unknown>) => (
        <span style={{ fontFamily: "monospace" }}>
          {(config.bot_prefix as string) || "-"}
        </span>
      ),
    },
    {
      title: t("channels.actions"),
      key: "actions",
      width: 150,
      render: (_: unknown, record: any) => (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Button
            type="link"
            size="small"
            onClick={() => handleEdit(record.key)}
          >
            {t("channels.configure")}
          </Button>
        </div>
      ),
    },
  ];

  const FILTER_TABS: { key: FilterType; label: string }[] = [
    { key: "all", label: t("channels.filterAll") },
    { key: "builtin", label: t("channels.builtin") },
    { key: "custom", label: t("channels.custom") },
  ];

  return (
    <div className={styles.channelsPage}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.title}>{t("channels.title")}</h1>
          <p className={styles.description}>{t("channels.description")}</p>
        </div>
        <div className={styles.filterTabs}>
          {FILTER_TABS.map(({ key, label }) => (
            <button
              key={key}
              className={`${styles.filterTab} ${
                filter === key ? styles.filterTabActive : ""
              }`}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
        <Table
          columns={columns}
          dataSource={tableData}
          loading={loading}
          rowKey="key"
          pagination={{
            pageSize: 10,
            showSizeChanger: false,
            showTotal: (total: number) => t("channels.totalItems", { count: total }),
          }}
          size="small"
        />
      </Card>

      <ChannelDrawer
        open={drawerOpen}
        activeKey={activeKey}
        activeLabel={activeLabel}
        form={form}
        saving={saving}
        initialValues={activeKey ? channels[activeKey] : undefined}
        isBuiltin={activeKey ? isBuiltin(activeKey) : true}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default ChannelsPage;
