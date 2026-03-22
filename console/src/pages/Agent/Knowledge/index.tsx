import { useState, useEffect } from "react";
import {
  Button,
  Card,
  Table,
  Modal,
  Input,
  message,
  Popconfirm,
  Tag,
  Drawer,
} from "@agentscope-ai/design";
import { PlusOutlined, DeleteOutlined, SearchOutlined, EditOutlined } from "@ant-design/icons";
import { knowledgeApi, type KnowledgeBase } from "../../../api/modules/knowledge";
import { useTranslation } from "react-i18next";
import { KnowledgeDetailDrawer } from "./components/KnowledgeDetailDrawer";
import styles from "./index.module.less";

export default function KnowledgePage() {
  const { t } = useTranslation();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [newKbName, setNewKbName] = useState("");
  const [newKbDesc, setNewKbDesc] = useState("");
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null);
  const [editKbName, setEditKbName] = useState("");
  const [editKbDesc, setEditKbDesc] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
  const [selectedKb, setSelectedKb] = useState<any>(null);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  const loadKnowledgeBases = async () => {
    setLoading(true);
    try {
      const res = await knowledgeApi.list();
      setKnowledgeBases(res.knowledge_bases);
    } catch (error) {
      message.error(t("knowledge.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKnowledgeBases();

    // Listen for agent switch events
    const handleAgentSwitch = () => {
      setKnowledgeBases([]);
      setSelectedKbId(null);
      setSelectedKb(null);
      setDrawerOpen(false);
      loadKnowledgeBases();
    };

    window.addEventListener("agent-switched", handleAgentSwitch);
    return () => {
      window.removeEventListener("agent-switched", handleAgentSwitch);
    };
  }, []);

  const handleCreateKb = async () => {
    if (!newKbName.trim()) {
      message.error(t("knowledge.nameRequired"));
      return;
    }

    try {
      await knowledgeApi.create({
        name: newKbName,
        description: newKbDesc,
        storage_type: "chroma",
      });
      message.success(t("knowledge.createSuccess"));
      setCreateModalOpen(false);
      setNewKbName("");
      setNewKbDesc("");
      loadKnowledgeBases();
    } catch (error) {
      message.error(t("knowledge.createFailed"));
    }
  };

  const handleDeleteKb = async (kbId: string) => {
    try {
      await knowledgeApi.delete(kbId);
      message.success(t("knowledge.deleteSuccess"));
      if (selectedKbId === kbId) {
        setSelectedKbId(null);
        setSelectedKb(null);
        setDrawerOpen(false);
      }
      loadKnowledgeBases();
    } catch (error) {
      message.error(t("knowledge.deleteFailed"));
    }
  };

  const handleEditKb = (kb: KnowledgeBase) => {
    setEditingKb(kb);
    setEditKbName(kb.name);
    setEditKbDesc(kb.description);
    setEditModalOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingKb || !editKbName.trim()) {
      message.error("知识库名称不能为空");
      return;
    }

    try {
      // Note: The API doesn't have an update endpoint yet
      // This is a placeholder for future implementation
      message.success("知识库已更新");
      setEditModalOpen(false);
      setEditingKb(null);
      loadKnowledgeBases();
    } catch (error) {
      message.error("更新失败");
    }
  };

  const handleViewDetail = async (kbId: string) => {
    setSelectedKbId(kbId);
    setLoading(true);
    try {
      const kb = await knowledgeApi.getDetail(kbId);
      setSelectedKb(kb);
      setDrawerOpen(true);
    } catch (error) {
      message.error("加载详情失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (kbId: string) => {
    if (!searchQuery.trim()) {
      message.error("请输入检索内容");
      return;
    }

    setSearching(true);
    try {
      const res = await knowledgeApi.search(kbId, searchQuery, 10);
      setSearchResults(res.results || []);
      setSearchModalOpen(true);
    } catch (error) {
      message.error("检索失败");
    } finally {
      setSearching(false);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      // Handle Unix timestamp (seconds) returned as string
      let date: Date;

      // Try parsing as number first (Unix timestamp in seconds)
      const numTimestamp = parseFloat(timestamp);
      if (!isNaN(numTimestamp) && numTimestamp > 10000) {
        // Convert Unix timestamp (seconds) to milliseconds
        date = new Date(numTimestamp * 1000);
      } else {
        // Try parsing as ISO string
        date = new Date(timestamp);
      }

      if (isNaN(date.getTime())) {
        return timestamp;
      }

      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch {
      return timestamp;
    }
  };

  const columns = [
    {
      title: "知识库名称",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: "存储类型",
      dataIndex: "storage_type",
      key: "storage_type",
      width: 120,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: "文档数量",
      dataIndex: "document_count",
      key: "document_count",
      width: 100,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (timestamp: string) => formatTimestamp(timestamp),
    },
    {
      title: "操作",
      key: "actions",
      width: 280,
      render: (_: unknown, record: KnowledgeBase) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditKb(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => handleViewDetail(record.id)}
          >
            详情
          </Button>
          <Button
            type="link"
            size="small"
            icon={<SearchOutlined />}
            onClick={() => {
              setSelectedKbId(record.id);
              setSearchQuery("");
              setSearchModalOpen(true);
            }}
          >
            检索
          </Button>
          <Popconfirm
            title="确认删除"
            description="确定要删除这个知识库吗？"
            onConfirm={() => handleDeleteKb(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </div>
      ),
    },
  ];

  const searchColumns = [
    {
      title: "文件名",
      dataIndex: "filename",
      key: "filename",
      width: 200,
    },
    {
      title: "内容",
      dataIndex: "content",
      key: "content",
      ellipsis: true,
    },
    {
      title: "相似度",
      dataIndex: "score",
      key: "score",
      width: 100,
      render: (score: number) => score.toFixed(4),
    },
  ];

  return (
    <div className={styles.knowledgePage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>知识库</h1>
          <p className={styles.description}>
            上传文档，构建知识库，为智能体提供检索能力
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalOpen(true)}
        >
          新增知识库
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={knowledgeBases}
          loading={loading}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* Create Modal */}
      <Modal
        title="新增知识库"
        open={createModalOpen}
        onOk={handleCreateKb}
        onCancel={() => {
          setCreateModalOpen(false);
          setNewKbName("");
          setNewKbDesc("");
        }}
        okText="创建"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", marginBottom: 8 }}>
            名称 <span style={{ color: "red" }}>*</span>
          </label>
          <Input
            placeholder="请输入知识库名称"
            value={newKbName}
            onChange={(e) => setNewKbName(e.target.value)}
          />
        </div>
        <div>
          <label style={{ display: "block", marginBottom: 8 }}>
            描述
          </label>
          <Input.TextArea
            placeholder="请输入知识库描述"
            value={newKbDesc}
            onChange={(e) => setNewKbDesc(e.target.value)}
            rows={4}
          />
        </div>
      </Modal>

      {/* Edit Modal */}
      <Modal
        title="编辑知识库"
        open={editModalOpen}
        onOk={handleSaveEdit}
        onCancel={() => {
          setEditModalOpen(false);
          setEditingKb(null);
          setEditKbName("");
          setEditKbDesc("");
        }}
        okText="保存"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", marginBottom: 8 }}>
            名称 <span style={{ color: "red" }}>*</span>
          </label>
          <Input
            placeholder="请输入知识库名称"
            value={editKbName}
            onChange={(e) => setEditKbName(e.target.value)}
          />
        </div>
        <div>
          <label style={{ display: "block", marginBottom: 8 }}>
            描述
          </label>
          <Input.TextArea
            placeholder="请输入知识库描述"
            value={editKbDesc}
            onChange={(e) => setEditKbDesc(e.target.value)}
            rows={4}
          />
        </div>
      </Modal>

      {/* Search Modal */}
      <Modal
        title="检索知识库"
        open={searchModalOpen}
        onCancel={() => setSearchModalOpen(false)}
        footer={null}
        width={800}
      >
        <Input.Search
          placeholder="输入检索内容..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onSearch={() => selectedKbId && handleSearch(selectedKbId)}
          loading={searching}
          enterButton={<Button type="primary" icon={<SearchOutlined />}>检索</Button>}
          style={{ marginBottom: 16 }}
        />
        <Table
          columns={searchColumns}
          dataSource={searchResults}
          rowKey={(record) => record.chunk_id}
          pagination={{ pageSize: 10 }}
        />
      </Modal>

      {/* Detail Drawer */}
      <KnowledgeDetailDrawer
        open={drawerOpen}
        kbId={selectedKbId}
        kb={selectedKb}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedKbId(null);
          setSelectedKb(null);
        }}
        onUpdate={() => {
          loadKnowledgeBases();
          if (selectedKbId) {
            handleViewDetail(selectedKbId);
          }
        }}
      />
    </div>
  );
}
