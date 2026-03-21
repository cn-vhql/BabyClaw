import { useState } from "react";
import { Button, Table, Card, Tag, Modal, message } from "@agentscope-ai/design";
import { PlusOutlined } from "@ant-design/icons";
import { useProviders } from "./useProviders";
import {
  PageHeader,
  LoadingState,
  CustomProviderModal,
  ProviderConfigModal,
  ModelManageModal,
  EmbeddingConfigModal,
} from "./components";
import { useTranslation } from "react-i18next";
import type { ProviderInfo } from "../../../api/types/provider";
import api from "../../../api";
import styles from "./index.module.less";

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

function ModelsPage() {
  const { t } = useTranslation();
  const { providers, activeModels, loading, error, fetchAll } = useProviders();
  const [addProviderOpen, setAddProviderOpen] = useState(false);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [modelManageOpen, setModelManageOpen] = useState(false);
  const [embeddingConfigOpen, setEmbeddingConfigOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<ProviderInfo | null>(null);

  const refreshProvidersSilently = () => fetchAll(false);


  const handleManageModels = (provider: ProviderInfo) => {
    setSelectedProvider(provider);
    setModelManageOpen(true);
  };

  const handleConfigure = (provider: ProviderInfo) => {
    setSelectedProvider(provider);
    setConfigModalOpen(true);
  };

  const handleDeleteProvider = (provider: ProviderInfo) => {
    Modal.confirm({
      title: t("models.deleteProvider"),
      content: t("models.deleteProviderConfirm", { name: provider.name }),
      okText: t("common.delete"),
      okButtonProps: { danger: true },
      cancelText: t("common.cancel"),
      onOk: async () => {
        try {
          await api.deleteCustomProvider(provider.id);
          message.success(t("models.providerDeleted", { name: provider.name }));
          refreshProvidersSilently();
        } catch (error) {
          const errMsg =
            error instanceof Error
              ? error.message
              : t("models.providerDeleteFailed");
          message.error(errMsg);
        }
      },
    });
  };

  const getProviderStatus = (provider: ProviderInfo) => {
    const totalCount = provider.models.length + provider.extra_models.length;

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

    const hasModels = totalCount > 0;
    const isAvailable = isConfigured && hasModels;

    return {
      isAvailable,
      isConfigured,
      hasModels,
      totalCount,
      statusLabel: isAvailable
        ? t("models.providerAvailable")
        : isConfigured
        ? t("models.providerNoModels")
        : t("models.providerNotConfigured"),
      statusType: isAvailable
        ? "enabled"
        : isConfigured
        ? "partial"
        : "disabled",
      statusDotColor: isAvailable
        ? "#52c41a"
        : isConfigured
        ? "#faad14"
        : "#d9d9d9",
    };
  };

  const columns = [
    {
      title: t("models.name"),
      dataIndex: "name",
      key: "name",
      ellipsis: true,
      render: (name: string, record: ProviderInfo) => (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>{name}</span>
          {record.is_custom ? (
            <Tag color="blue" style={{ fontSize: 11 }}>
              {t("models.custom")}
            </Tag>
          ) : (
            <Tag color="green" style={{ fontSize: 11 }}>
              {t("models.builtin")}
            </Tag>
          )}
        </div>
      ),
    },
    {
      title: t("models.providerType"),
      key: "providerType",
      width: 100,
      render: (_: unknown, record: ProviderInfo) => (
        <Tag color={record.is_local ? "purple" : "cyan"} style={{ fontSize: 11 }}>
          {record.is_local ? t("models.local") : t("models.remote")}
        </Tag>
      ),
    },
    {
      title: t("models.status"),
      key: "status",
      width: 150,
      render: (_: unknown, record: ProviderInfo) => {
        const { statusLabel, statusDotColor } = getProviderStatus(record);
        return (
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: statusDotColor,
                boxShadow: statusDotColor === "#52c41a" ? "0 0 0 2px rgba(82, 196, 26, 0.2)" : "none",
              }}
            />
            <span style={{ fontSize: 12 }}>{statusLabel}</span>
          </div>
        );
      },
    },
    {
      title: t("models.baseURL"),
      dataIndex: "base_url",
      key: "base_url",
      ellipsis: true,
      render: (base_url: string) => base_url || "-",
    },
    {
      title: t("models.apiKey"),
      dataIndex: "api_key",
      key: "api_key",
      ellipsis: true,
      render: (api_key: string) => api_key || "-",
    },
    {
      title: t("models.model"),
      key: "models",
      width: 120,
      render: (_: unknown, record: ProviderInfo) => {
        const totalCount = record.models.length + record.extra_models.length;
        return totalCount > 0
          ? t("models.modelsCount", { count: totalCount })
          : t("models.noModels");
      },
    },
    {
      title: t("models.actions"),
      key: "actions",
      width: 200,
      render: (_: unknown, record: ProviderInfo) => (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Button
            type="link"
            size="small"
            onClick={() => handleManageModels(record)}
          >
            {t("models.manageModels")}
          </Button>
          {!record.is_local && (
            <Button
              type="link"
              size="small"
              onClick={() => handleConfigure(record)}
            >
              {t("models.settings")}
            </Button>
          )}
          {record.is_custom && (
            <Button
              type="link"
              size="small"
              danger
              onClick={() => handleDeleteProvider(record)}
            >
              {t("common.delete")}
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className={styles.settingsPage}>
      {loading ? (
        <LoadingState message={t("models.loading")} />
      ) : error ? (
        <LoadingState message={error} error onRetry={fetchAll} />
      ) : (
        <>
          {/* ---- Providers Section ---- */}
          <div className={styles.providersBlock}>
            <div className={styles.sectionHeaderRow}>
              <PageHeader
                title={t("models.providersTitle")}
                description={t("models.providersDescription")}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <Button
                  onClick={() => setEmbeddingConfigOpen(true)}
                  className={styles.addProviderBtn}
                >
                  {t("models.embedding.configButton")}
                </Button>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setAddProviderOpen(true)}
                  className={styles.addProviderBtn}
                >
                  {t("models.addProvider")}
                </Button>
              </div>
            </div>

            {providers.length > 0 && (
              <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
                <Table
                  columns={columns}
                  dataSource={providers}
                  rowKey="id"
                  pagination={{
                    pageSize: 10,
                    showSizeChanger: false,
                    showTotal: (total) => t("models.totalItems", { count: total }),
                  }}
                  size="small"
                />
              </Card>
            )}
          </div>

          <CustomProviderModal
            open={addProviderOpen}
            onClose={() => setAddProviderOpen(false)}
            onSaved={fetchAll}
          />

          {selectedProvider && !selectedProvider.is_local && (
            <ProviderConfigModal
              provider={selectedProvider}
              activeModels={activeModels}
              open={configModalOpen}
              onClose={() => {
                setConfigModalOpen(false);
                setSelectedProvider(null);
              }}
              onSaved={refreshProvidersSilently}
            />
          )}

          {selectedProvider && (
            <ModelManageModal
              provider={selectedProvider}
              open={modelManageOpen}
              onClose={() => {
                setModelManageOpen(false);
                setSelectedProvider(null);
              }}
              onSaved={refreshProvidersSilently}
            />
          )}

          <EmbeddingConfigModal
            open={embeddingConfigOpen}
            onClose={() => setEmbeddingConfigOpen(false)}
            onSaved={refreshProvidersSilently}
          />
        </>
      )}
    </div>
  );
}

export default ModelsPage;
