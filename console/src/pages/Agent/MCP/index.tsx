import { useState } from "react";
import { Button, Table, Card, Tag, Switch, Modal, Input, Empty } from "@agentscope-ai/design";
import type { MCPClientInfo } from "../../../api/types";
import { useMCP } from "./useMCP";
import { useTranslation } from "react-i18next";
import styles from "./index.module.less";

type MCPTransport = "stdio" | "streamable_http" | "sse";

function normalizeTransport(raw?: unknown): MCPTransport | undefined {
  if (typeof raw !== "string") return undefined;
  const value = raw.trim().toLowerCase();
  switch (value) {
    case "stdio":
      return "stdio";
    case "sse":
      return "sse";
    case "streamablehttp":
    case "streamable_http":
    case "streamable-http":
    case "http":
      return "streamable_http";
    default:
      return undefined;
  }
}

function normalizeClientData(key: string, rawData: any) {
  const transport =
    normalizeTransport(rawData.transport ?? rawData.type) ??
    (rawData.url || rawData.baseUrl || !rawData.command
      ? "streamable_http"
      : "stdio");

  const command =
    transport === "stdio" ? (rawData.command ?? "").toString() : "";

  return {
    name: rawData.name || key,
    description: rawData.description || "",
    enabled: rawData.enabled ?? rawData.isActive ?? true,
    transport,
    url: (rawData.url || rawData.baseUrl || "").toString(),
    headers: rawData.headers || {},
    command,
    args: Array.isArray(rawData.args) ? rawData.args : [],
    env: rawData.env || {},
    cwd: (rawData.cwd || "").toString(),
  };
}

function MCPPage() {
  const { t } = useTranslation();
  const {
    clients,
    loading,
    toggleEnabled,
    deleteClient,
    createClient,
    updateClient,
  } = useMCP();
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [selectedClient, setSelectedClient] = useState<MCPClientInfo | null>(null);
  const [editedJson, setEditedJson] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newClientJson, setNewClientJson] = useState(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);

  const handleToggleEnabled = async (client: MCPClientInfo) => {
    await toggleEnabled(client);
  };

  const handleDeleteClick = (client: MCPClientInfo) => {
    setSelectedClient(client);
    setDeleteModalOpen(true);
  };

  const confirmDelete = async () => {
    if (selectedClient) {
      await deleteClient(selectedClient);
      setDeleteModalOpen(false);
      setSelectedClient(null);
    }
  };

  const handleEditClick = (client: MCPClientInfo) => {
    const jsonStr = JSON.stringify(client, null, 2);
    setEditedJson(jsonStr);
    setIsEditing(false);
    setSelectedClient(client);
    setJsonModalOpen(true);
  };

  const handleSaveJson = async () => {
    if (!selectedClient) return;
    try {
      const parsed = JSON.parse(editedJson);
      const { key, ...updates } = parsed;
      const success = await updateClient(selectedClient.key, updates);
      if (success) {
        setJsonModalOpen(false);
        setIsEditing(false);
        setSelectedClient(null);
      }
    } catch (error) {
      alert("Invalid JSON format");
    }
  };

  const handleCreateClient = async () => {
    try {
      const parsed = JSON.parse(newClientJson);

      // Support two formats:
      // Format 1: { "mcpServers": { "key": { "command": "...", ... } } }
      // Format 2: { "key": { "command": "...", ... } }
      // Format 3: { "key": "...", "name": "...", "command": "...", ... } (direct)

      const clientsToCreate: Array<{ key: string; data: any }> = [];

      if (parsed.mcpServers) {
        // Format 1: nested mcpServers
        Object.entries(parsed.mcpServers).forEach(
          ([key, data]: [string, any]) => {
            clientsToCreate.push({
              key,
              data: normalizeClientData(key, data),
            });
          },
        );
      } else if (
        parsed.key &&
        (parsed.command || parsed.url || parsed.baseUrl)
      ) {
        // Format 3: direct format with key field
        const { key, ...clientData } = parsed;
        clientsToCreate.push({
          key,
          data: normalizeClientData(key, clientData),
        });
      } else {
        // Format 2: direct client objects with keys
        Object.entries(parsed).forEach(([key, data]: [string, any]) => {
          if (
            typeof data === "object" &&
            (data.command || data.url || data.baseUrl)
          ) {
            clientsToCreate.push({
              key,
              data: normalizeClientData(key, data),
            });
          }
        });
      }

      // Create all clients
      let allSuccess = true;
      for (const { key, data } of clientsToCreate) {
        const success = await createClient(key, data);
        if (!success) allSuccess = false;
      }

      if (allSuccess) {
        setCreateModalOpen(false);
        setNewClientJson(`{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`);
      }
    } catch (error) {
      alert("Invalid JSON format");
    }
  };

  const columns = [
    {
      title: t("mcp.name"),
      dataIndex: "name",
      key: "name",
      ellipsis: true,
    },
    {
      title: t("mcp.type"),
      dataIndex: "transport",
      key: "type",
      width: 120,
      render: (transport: string) => {
        const isRemote = transport === "streamable_http" || transport === "sse";
        return (
          <Tag color={isRemote ? "orange" : "blue"}>
            {isRemote ? t("mcp.remote") : t("mcp.local")}
          </Tag>
        );
      },
    },
    {
      title: t("mcp.description"),
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (description: string) => description || "-",
    },
    {
      title: t("mcp.status"),
      dataIndex: "enabled",
      key: "status",
      width: 100,
      render: (enabled: boolean, record: MCPClientInfo) => (
        <Switch
          size="small"
          checked={enabled}
          onChange={() => handleToggleEnabled(record)}
        />
      ),
    },
    {
      title: t("mcp.actions"),
      key: "actions",
      width: 200,
      render: (_: unknown, record: MCPClientInfo) => (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Button
            type="link"
            size="small"
            onClick={() => handleEditClick(record)}
          >
            {t("common.edit")}
          </Button>
          <Button
            type="link"
            size="small"
            danger
            onClick={() => handleDeleteClick(record)}
            disabled={record.enabled}
          >
            {t("common.delete")}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className={styles.mcpPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{t("mcp.title")}</h1>
          <p className={styles.description}>{t("mcp.description")}</p>
        </div>
        <Button type="primary" onClick={() => setCreateModalOpen(true)}>
          {t("mcp.create")}
        </Button>
      </div>

      {loading ? (
        <div className={styles.loading}>
          <p>{t("common.loading")}</p>
        </div>
      ) : clients.length === 0 ? (
        <Empty description={t("mcp.emptyState")} />
      ) : (
        <Card className={styles.tableCard} bodyStyle={{ padding: 0 }}>
          <Table
            columns={columns}
            dataSource={clients}
            rowKey="key"
            pagination={{
              pageSize: 10,
              showSizeChanger: false,
              showTotal: (total) => t("mcp.totalItems", { count: total }),
            }}
            size="small"
          />
        </Card>
      )}

      {/* Create Modal */}
      <Modal
        title={t("mcp.create")}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => setCreateModalOpen(false)}
              style={{ marginRight: 8 }}
            >
              {t("common.cancel")}
            </Button>
            <Button type="primary" onClick={handleCreateClient}>
              {t("common.create")}
            </Button>
          </div>
        }
        width={800}
      >
        <div style={{ marginBottom: 12 }}>
          <p style={{ margin: 0, fontSize: 13, color: "#666" }}>
            {t("mcp.formatSupport")}:
          </p>
          <ul
            style={{
              margin: "8px 0",
              padding: "0 0 0 20px",
              fontSize: 12,
              color: "#999",
            }}
          >
            <li>
              Standard format:{" "}
              <code>{`{ "mcpServers": { "key": {...} } }`}</code>
            </li>
            <li>
              Direct format: <code>{`{ "key": {...} }`}</code>
            </li>
            <li>
              Single format:{" "}
              <code>{`{ "key": "...", "name": "...", "command": "..." }`}</code>
            </li>
          </ul>
        </div>
        <Input.TextArea
          value={newClientJson}
          onChange={(e) => setNewClientJson(e.target.value)}
          autoSize={{ minRows: 15, maxRows: 25 }}
          style={{
            fontFamily: "Monaco, Courier New, monospace",
            fontSize: 13,
          }}
        />
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        title={t("common.confirm")}
        open={deleteModalOpen}
        onOk={confirmDelete}
        onCancel={() => {
          setDeleteModalOpen(false);
          setSelectedClient(null);
        }}
        okText={t("common.confirm")}
        cancelText={t("common.cancel")}
        okButtonProps={{ danger: true }}
      >
        <p>{t("mcp.deleteConfirm")}</p>
      </Modal>

      {/* Edit JSON Modal */}
      <Modal
        title={selectedClient ? `${selectedClient.name} - ${t("common.configuration")}` : t("common.configuration")}
        open={jsonModalOpen}
        onCancel={() => {
          setJsonModalOpen(false);
          setIsEditing(false);
          setSelectedClient(null);
        }}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => {
                setJsonModalOpen(false);
                setIsEditing(false);
                setSelectedClient(null);
              }}
              style={{ marginRight: 8 }}
            >
              {t("common.cancel")}
            </Button>
            {isEditing ? (
              <Button type="primary" onClick={handleSaveJson}>
                {t("common.save")}
              </Button>
            ) : (
              <Button type="primary" onClick={() => setIsEditing(true)}>
                {t("common.edit")}
              </Button>
            )}
          </div>
        }
        width={700}
      >
        {isEditing ? (
          <Input.TextArea
            value={editedJson}
            onChange={(e) => setEditedJson(e.target.value)}
            autoSize={{ minRows: 15, maxRows: 25 }}
            style={{
              fontFamily: "Monaco, Courier New, monospace",
              fontSize: 13,
            }}
          />
        ) : (
          <pre
            style={{
              backgroundColor: "#f5f5f5",
              color: "rgba(0,0,0,0.88)",
              padding: 16,
              borderRadius: 8,
              maxHeight: 500,
              overflow: "auto",
            }}
          >
            {editedJson}
          </pre>
        )}
      </Modal>
    </div>
  );
}

export default MCPPage;
