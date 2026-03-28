import { useState, useEffect, useMemo } from "react";
import { Card, Select, Button, message } from "@agentscope-ai/design";
import { Spin } from "antd";
import {
  CheckOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { providerApi } from "../../../../../api/modules/provider";
import { useAgentStore } from "../../../../../stores/agentStore";
import type { ProviderInfo, ActiveModelsInfo } from "../../../../../api/types";
import styles from "../../index.module.less";

interface ModelOption {
  label: string;
  value: string;
  providerId: string;
  providerName: string;
  modelName: string;
}

export function AgentDefaultModelCard({
  providers,
  activeModels,
  onUpdated,
}: {
  providers: ProviderInfo[];
  activeModels: ActiveModelsInfo | null;
  onUpdated: () => void;
}) {
  const { t } = useTranslation();
  const { selectedAgent, agents } = useAgentStore();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentAgentName, setCurrentAgentName] = useState<string>("");

  // Get current agent name
  useEffect(() => {
    const agent = agents.find((a) => a.id === selectedAgent);
    setCurrentAgentName(agent?.name || selectedAgent);
  }, [selectedAgent, agents]);

  // Build model options from all providers
  const modelOptions = useMemo(() => {
    const options: ModelOption[] = [];

    for (const provider of providers) {
      const hasModels =
        (provider.models?.length ?? 0) + (provider.extra_models?.length ?? 0) > 0;

      if (!hasModels) continue;

      // Check if provider is configured
      let isConfigured = false;
      if (provider.is_local) {
        isConfigured = true;
      } else if (provider.is_custom && provider.base_url) {
        isConfigured = true;
      } else if (provider.require_api_key === false) {
        isConfigured = true;
      } else if (provider.require_api_key && provider.api_key) {
        isConfigured = true;
      }

      if (!isConfigured) continue;

      // Add all models from this provider
      const allModels = [...(provider.models ?? []), ...(provider.extra_models ?? [])];
      for (const model of allModels) {
        options.push({
          label: `${provider.name} - ${model.name || model.id}`,
          value: `${provider.id}::${model.id}`,
          providerId: provider.id,
          providerName: provider.name,
          modelName: model.id,
        });
      }
    }

    return options;
  }, [providers]);

  // Get current active model value
  const currentValue = useMemo(() => {
    if (!activeModels?.active_llm) return undefined;
    const { provider_id, model } = activeModels.active_llm;
    return `${provider_id}::${model}`;
  }, [activeModels]);

  const handleChange = async (value: string) => {
    const [providerId, modelId] = value.split("::");
    if (!providerId || !modelId) return;

    setSaving(true);
    try {
      await providerApi.setActiveLlm({
        provider_id: providerId,
        model: modelId,
      });
      message.success(t("models.defaultModelUpdated"));
      onUpdated();
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : t("models.updateFailed");
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await onUpdated();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className={styles.agentDefaultModelCard}>
      <div className={styles.cardHeader}>
        <div className={styles.headerLeft}>
          <h3 className={styles.cardTitle}>
            {t("models.agentDefaultModel")}
          </h3>
          <span className={styles.agentNameBadge}>{currentAgentName}</span>
        </div>
        <Button
          size="small"
          icon={<SwapOutlined />}
          onClick={handleRefresh}
          loading={loading}
        >
          {t("common.refresh")}
        </Button>
      </div>

      <p className={styles.cardDescription}>
        {t("models.agentDefaultModelDesc")}
      </p>

      {saving ? (
        <div className={styles.savingWrapper}>
          <Spin size="small" />
          <span>{t("models.updating")}...</span>
        </div>
      ) : (
        <Select
          value={currentValue}
          onChange={handleChange}
          options={modelOptions}
          placeholder={t("models.selectDefaultModel")}
          className={styles.modelSelect}
          suffixIcon={currentValue ? <CheckOutlined /> : undefined}
          showSearch
          filterOption={(input, option) =>
            (option?.label ?? "").toLowerCase().includes(input.toLowerCase())
          }
          notFoundContent={t("models.noAvailableModels")}
        />
      )}
    </Card>
  );
}
