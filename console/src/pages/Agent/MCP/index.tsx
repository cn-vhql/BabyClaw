import { useState } from "react";
import {
  Button,
  Table,
  Tag,
  Switch,
  Modal,
  Input,
  Empty,
  message,
  Spinner,
} from "@agentscope-ai/design";
import { List, Typography } from "antd";
import { ApiOutlined, CheckCircleOutlined, CloseCircleOutlined } from "@ant-design/icons";
import type { MCPClientInfo } from "../../../api/types";
import { useMCP } from "./useMCP";
import { useTranslation } from "react-i18next";
import { mcpApi } from "../../../api/modules/mcp";
import styles from "./index.module.less";

const { Text, Paragraph } = Typography;

type MCPTransport = "stdio" | "streamable_http" | "sse";
type MCPTestResult = Awaited<ReturnType<typeof mcpApi.testMCPClient>>;
type MCPTestTool = MCPTestResult["tools"][number];
type RawMCPClientConfig = Record<string, unknown> & {
  name?: string;
  description?: string;
  enabled?: boolean;
  isActive?: boolean;
  transport?: unknown;
  type?: unknown;
  url?: unknown;
  baseUrl?: unknown;
  command?: unknown;
  headers?: unknown;
  args?: unknown;
  env?: unknown;
  cwd?: unknown;
};

function toStringMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return Object.entries(value).reduce<Record<string, string>>((acc, [key, val]) => {
    if (typeof val === "string") {
      acc[key] = val;
    }
    return acc;
  }, {});
}

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

function normalizeClientData(key: string, rawData: RawMCPClientConfig) {
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
    headers: toStringMap(rawData.headers),
    command,
    args: Array.isArray(rawData.args)
      ? rawData.args.filter((arg): arg is string => typeof arg === "string")
      : [],
    env: toStringMap(rawData.env),
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

  // Test connection states
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [testingClient, setTestingClient] = useState<MCPClientInfo | null>(null);
  const [testResult, setTestResult] = useState<MCPTestResult | null>(null);
  const [testing, setTesting] = useState(false);

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
      const { key, ...updates } = parsed as MCPClientInfo;
      void key;
      const success = await updateClient(selectedClient.key, updates);
      if (success) {
        setJsonModalOpen(false);
        setIsEditing(false);
        setSelectedClient(null);
      }
    } catch {
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

      const clientsToCreate: Array<{
        key: string;
        data: ReturnType<typeof normalizeClientData>;
      }> = [];

      if (parsed.mcpServers) {
        // Format 1: nested mcpServers
        Object.entries(parsed.mcpServers as Record<string, unknown>).forEach(
          ([key, data]) => {
            if (data && typeof data === "object" && !Array.isArray(data)) {
              clientsToCreate.push({
                key,
                data: normalizeClientData(key, data as RawMCPClientConfig),
              });
            }
          },
        );
      } else if (
        parsed.key &&
        (parsed.command || parsed.url || parsed.baseUrl)
      ) {
        // Format 3: direct format with key field
        const { key, ...clientData } = parsed as RawMCPClientConfig & {
          key: string;
        };
        clientsToCreate.push({
          key,
          data: normalizeClientData(key, clientData),
        });
      } else {
        // Format 2: direct client objects with keys
        Object.entries(parsed as Record<string, unknown>).forEach(([key, data]) => {
          if (typeof data === "object" && data !== null && !Array.isArray(data)) {
            const clientData = data as RawMCPClientConfig;
            if (clientData.command || clientData.url || clientData.baseUrl) {
              clientsToCreate.push({
                key,
                data: normalizeClientData(key, clientData),
              });
            }
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
    } catch {
      alert("Invalid JSON format");
    }
  };

  const handleTestClick = async (client: MCPClientInfo) => {
    setTestingClient(client);
    setTestResult(null);
    setTestModalOpen(true);
    setTesting(true);

    try {
      const result = await mcpApi.testMCPClient(client.key);
      setTestResult(result);

      if (result.connected) {
        message.success(`连接成功！发现 ${result.tool_count || 0} 个工具`);
      } else {
        message.error(`连接失败: ${result.error || "未知错误"}`);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "测试失败";
      setTestResult({
        client_key: client.key,
        client_name: client.name,
        connected: false,
        error: errorMsg,
        tools: [],
        tool_count: 0,
      });
      message.error(`测试失败: ${errorMsg}`);
    } finally {
      setTesting(false);
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
      className: "copaw-table-actions-cell",
      onHeaderCell: () => ({ className: "copaw-table-actions-cell" }),
      width: 200,
      render: (_: unknown, record: MCPClientInfo) => (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Button
            type="link"
            size="small"
            icon={<ApiOutlined />}
            onClick={() => handleTestClick(record)}
          >
            测试
          </Button>
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

      {/* Test Connection Modal */}
      <Modal
        title={testingClient ? `测试连接 - ${testingClient.name}` : "测试连接"}
        open={testModalOpen}
        onCancel={() => {
          setTestModalOpen(false);
          setTestingClient(null);
          setTestResult(null);
        }}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => {
                setTestModalOpen(false);
                setTestingClient(null);
                setTestResult(null);
              }}
            >
              关闭
            </Button>
          </div>
        }
        width={800}
      >
        <div style={{ minHeight: 400 }}>
          {testing ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 400,
              }}
            >
              <Spinner />
              <div style={{ marginTop: 16, color: "#666" }}>
                正在测试连接...
              </div>
            </div>
          ) : testResult ? (
            <div>
              {/* Connection Status */}
              <div
                style={{
                  marginBottom: 24,
                  padding: 16,
                  borderRadius: 8,
                  backgroundColor: testResult.connected ? "#f6ffed" : "#fff2f0",
                  border: `1px solid ${testResult.connected ? "#b7eb8f" : "#ffccc7"}`,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {testResult.connected ? (
                    <CheckCircleOutlined style={{ fontSize: 24, color: "#52c41a" }} />
                  ) : (
                    <CloseCircleOutlined style={{ fontSize: 24, color: "#ff4d4f" }} />
                  )}
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                      {testResult.connected ? "连接成功" : "连接失败"}
                    </div>
                    {testResult.error && (
                      <div style={{ fontSize: 13, color: "#ff4d4f" }}>
                        错误信息: {testResult.error}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Tools List */}
              {testResult.connected && testResult.tools && testResult.tools.length > 0 ? (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ fontSize: 14 }}>
                      可用工具 ({testResult.tool_count || testResult.tools.length} 个)
                    </Text>
                  </div>
                  <List
                    bordered
                    dataSource={testResult.tools}
                    renderItem={(tool: MCPTestTool, index: number) => (
                      <List.Item>
                        <div style={{ width: "100%" }}>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 12,
                              marginBottom: 8,
                            }}
                          >
                            <Tag color="blue" style={{ marginTop: 2 }}>
                              {index + 1}
                            </Tag>
                            <Text strong style={{ fontSize: 14 }}>
                              {tool.name}
                            </Text>
                          </div>
                          {tool.description && (
                            <Paragraph
                              style={{
                                marginLeft: 42,
                                marginBottom: 8,
                                color: "#666",
                                fontSize: 13,
                              }}
                            >
                              {String(tool.description)}
                            </Paragraph>
                          )}
                          {Boolean(tool.input_schema) && (
                            <div
                              style={{
                                marginLeft: 42,
                                padding: 12,
                                backgroundColor: "#f5f5f5",
                                borderRadius: 6,
                              }}
                            >
                              <Text
                                style={{
                                  fontSize: 12,
                                  color: "#999",
                                  display: "block",
                                  marginBottom: 8,
                                }}
                              >
                                参数定义:
                              </Text>
                              <pre
                                style={{
                                  margin: 0,
                                  fontSize: 12,
                                  overflow: "auto",
                                  maxHeight: 200,
                                }}
                              >
                                {JSON.stringify(tool.input_schema, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </List.Item>
                    )}
                    pagination={{
                      pageSize: 10,
                      size: "small",
                    }}
                  />
                </div>
              ) : testResult.connected ? (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    minHeight: 300,
                  }}
                >
                  <Empty
                    description="该MCP服务没有提供工具"
                    style={{ margin: 0 }}
                  />
                </div>
              ) : null}
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 400,
              }}
            >
              <Empty description="点击测试按钮开始测试" style={{ margin: 0 }} />
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}

export default MCPPage;
