import { useState, useEffect, useRef } from "react";
import {
  Button,
  Table,
  Modal,
  Input,
  Select,
  Upload,
  Tabs,
  Tag,
  message,
  Popconfirm,
} from "@agentscope-ai/design";
import {
  PlusOutlined,
  DeleteOutlined,
  UploadOutlined,
  FileTextOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import type { UploadFile } from "antd";
import { knowledgeApi, type KnowledgeBase, type KnowledgeBaseDetail, type Document, type Chunk } from "../../../api/modules/knowledge";
import { useTranslation } from "react-i18next";
import styles from "./index.module.less";

export default function KnowledgePage() {
  const { t } = useTranslation();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null);
  const [selectedKb, setSelectedKb] = useState<KnowledgeBaseDetail | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newKbName, setNewKbName] = useState("");
  const [newKbDesc, setNewKbDesc] = useState("");

  // Track if we're switching agents to prevent loading old data
  const isSwitchingAgent = useRef(false);
  const [uploadChunkType, setUploadChunkType] = useState<"length" | "separator" | "tfidf">("length");
  const [uploadMaxLength, setUploadMaxLength] = useState(500);
  const [uploadOverlap, setUploadOverlap] = useState(50);
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [_previewChunks, setPreviewChunks] = useState<Chunk[]>([]);
  const [activeTab, setActiveTab] = useState("documents");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [editingChunks, setEditingChunks] = useState<Chunk[]>([]);
  const [newChunkContent, setNewChunkContent] = useState("");
  const [savingChunks, setSavingChunks] = useState(false);
  const [currentPreviewDocId, setCurrentPreviewDocId] = useState<string | null>(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPageSize] = useState(10);
  const [addChunkModalOpen, setAddChunkModalOpen] = useState(false);
  const [reindexingStatus, setReindexingStatus] = useState<string | null>(null);
  const [searchPage, setSearchPage] = useState(1);
  const [searchPageSize, setSearchPageSize] = useState(10);

  const loadKnowledgeBases = async () => {
    setUploading(true);
    try {
      const res = await knowledgeApi.list();
      setKnowledgeBases(res.knowledge_bases);

      // Clear switching flag after list is loaded
      isSwitchingAgent.current = false;
    } catch (error) {
      message.error(t("knowledge.loadFailed"));
      isSwitchingAgent.current = false;
    } finally {
      setUploading(false);
    }
  };

  useEffect(() => {
    loadKnowledgeBases();
  }, []);

  // Listen for agent switch events
  useEffect(() => {
    const handleAgentSwitch = () => {
      // Set switching flag to prevent loading old data
      isSwitchingAgent.current = true;

      // Clear ALL current state immediately
      setKnowledgeBases([]);
      setSelectedKbId(null);
      setSelectedKb(null);
      setSearchResults([]);
      setSearchQuery("");
      setSearchPage(1);

      // Load knowledge bases for new agent
      // AgentSelector already has setTimeout, so localStorage should be updated
      loadKnowledgeBases();
    };

    // Listen for custom agent switch event
    window.addEventListener("agent-switched", handleAgentSwitch);

    return () => {
      window.removeEventListener("agent-switched", handleAgentSwitch);
    };
  }, []);

  // Auto-select first knowledge base when list loads (only on initial load or after agent switch)
  useEffect(() => {
    // Don't auto-select if we're switching agents (let the load complete first)
    if (isSwitchingAgent.current) {
      return;
    }

    if (knowledgeBases.length > 0 && !selectedKbId) {
      handleSelectKb(knowledgeBases[0].id);
    }
  }, [knowledgeBases]); // Only depend on knowledgeBases to avoid loops

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
      }
      loadKnowledgeBases();
    } catch (error) {
      message.error(t("knowledge.deleteFailed"));
    }
  };

  const handleSelectKb = async (kbId: string) => {
    // Prevent loading if we're switching agents
    if (isSwitchingAgent.current) {
      return;
    }

    setSelectedKbId(kbId);
    setUploading(true);

    // Clear search state when switching knowledge base
    setSearchResults([]);
    setSearchQuery("");
    setSearchPage(1);

    try {
      const kb = await knowledgeApi.getDetail(kbId);
      setSelectedKb(kb);
    } catch (error: any) {
      // If 404, knowledge base doesn't exist (possibly deleted or agent switched)
      if (error.message && error.message.includes("404")) {
        setSelectedKbId(null);
        setSelectedKb(null);
        // Reload list to get current state
        loadKnowledgeBases();
      } else {
        message.error(t("knowledge.loadDetailFailed"));
      }
    } finally {
      setUploading(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedKbId || uploadFiles.length === 0) {
      return;
    }

    setUploading(true);
    try {
      for (const file of uploadFiles) {
        const fileObj = file.originFileObj;
        if (fileObj) {
          await knowledgeApi.uploadDocument(
            selectedKbId,
            fileObj,
            {
              chunk_type: uploadChunkType,
              max_length: uploadMaxLength,
              overlap: uploadOverlap,
            }
          );
        }
      }
      message.success(t("knowledge.uploadSuccess"));
      setUploadFiles([]);
      if (selectedKbId) {
        handleSelectKb(selectedKbId);
      }
    } catch (error) {
      message.error(t("knowledge.uploadFailed"));
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedKbId) return;

    try {
      await knowledgeApi.deleteDocument(selectedKbId, docId);
      message.success(t("knowledge.deleteDocSuccess"));
      if (selectedKbId) {
        handleSelectKb(selectedKbId);
      }
    } catch (error) {
      message.error(t("knowledge.deleteDocFailed"));
    }
  };

  const handlePreviewChunks = async (docId: string) => {
    if (!selectedKbId) return;

    try {
      const res = await knowledgeApi.getChunks(selectedKbId, docId);
      setPreviewChunks(res.chunks);
      setEditingChunks(JSON.parse(JSON.stringify(res.chunks))); // Deep copy
      setCurrentPreviewDocId(docId);
      setPreviewPage(1); // Reset to first page
      setPreviewModalOpen(true);
    } catch (error) {
      message.error(t("knowledge.loadChunksFailed"));
    }
  };

  const handleSearch = async () => {
    if (!selectedKbId || !searchQuery.trim()) {
      return;
    }

    setSearching(true);
    setSearchPage(1); // Reset to first page when searching
    try {
      const res = await knowledgeApi.search(selectedKbId, searchQuery, 10);
      setSearchResults(res.results || []);
    } catch (error) {
      message.error(t("knowledge.searchFailed"));
    } finally {
      setSearching(false);
    }
  };

  const handleSaveChunks = async () => {
    if (!selectedKbId || !currentPreviewDocId) return;

    setSavingChunks(true);
    try {
      // Save all edited chunks first
      for (const chunk of editingChunks) {
        await knowledgeApi.updateChunk(
          selectedKbId,
          currentPreviewDocId,
          chunk.chunk_id,
          chunk.content
        );
      }

      message.success("保存成功！正在后台更新向量索引...");

      // Reindex in background, don't wait
      knowledgeApi.saveChunks(selectedKbId, currentPreviewDocId).then((res) => {
        setReindexingStatus(`索引更新完成：${res.embedding_count} 个向量`);
        setTimeout(() => setReindexingStatus(null), 5000);
      }).catch((err) => {
        console.error("Reindexing failed:", err);
        setReindexingStatus("索引更新失败");
        setTimeout(() => setReindexingStatus(null), 5000);
      });

      // Reload chunks to show saved state
      const chunksRes = await knowledgeApi.getChunks(selectedKbId, currentPreviewDocId);
      setPreviewChunks(chunksRes.chunks);
      setEditingChunks(JSON.parse(JSON.stringify(chunksRes.chunks)));

      // Refresh document list
      if (selectedKbId) {
        handleSelectKb(selectedKbId);
      }

      // Close modal after saving
      setPreviewModalOpen(false);
    } catch (error) {
      message.error("保存失败");
    } finally {
      setSavingChunks(false);
    }
  };

  const handleAddChunk = async () => {
    if (!newChunkContent.trim() || !selectedKbId || !currentPreviewDocId) {
      message.error("请输入内容");
      return;
    }

    try {
      const res = await knowledgeApi.addChunk(
        selectedKbId,
        currentPreviewDocId,
        newChunkContent
      );

      // Add to editing chunks
      const newChunk: Chunk = {
        chunk_id: res.chunk_id,
        content: newChunkContent,
        chunk_index: editingChunks.length,
      };
      const updatedChunks = [...editingChunks, newChunk];
      setEditingChunks(updatedChunks);

      // Jump to last page to see the new chunk
      const lastPage = Math.ceil(updatedChunks.length / previewPageSize);
      setPreviewPage(lastPage);

      // Clear and close modal
      setNewChunkContent("");
      setAddChunkModalOpen(false);

      message.success("添加成功，记得点击保存按钮以更新索引");
    } catch (error) {
      message.error("添加失败");
    }
  };

  const handleDeleteChunk = async (chunkId: string) => {
    if (!selectedKbId || !currentPreviewDocId) return;

    try {
      await knowledgeApi.deleteChunk(selectedKbId, currentPreviewDocId, chunkId);

      // Remove from editing chunks
      const newChunks = editingChunks.filter(c => c.chunk_id !== chunkId);
      // Reindex
      newChunks.forEach((c, idx) => c.chunk_index = idx);
      setEditingChunks(newChunks);

      // Adjust page if needed
      const maxPage = Math.max(1, Math.ceil(newChunks.length / previewPageSize));
      if (previewPage > maxPage) {
        setPreviewPage(maxPage);
      }

      message.success("删除成功，记得点击保存按钮以更新索引");
    } catch (error) {
      message.error("删除失败");
    }
  };

  const kbColumns = [
    {
      title: t("knowledge.name"),
      dataIndex: "name",
      key: "name",
    },
    {
      title: t("knowledge.description"),
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: t("knowledge.documentCount"),
      dataIndex: "document_count",
      key: "document_count",
      width: 100,
    },
    {
      title: t("knowledge.actions"),
      key: "actions",
      width: 150,
      render: (_: unknown, record: KnowledgeBase) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="link"
            size="small"
            onClick={() => handleSelectKb(record.id)}
          >
            查看
          </Button>
          <Popconfirm
            title={t("knowledge.deleteConfirm")}
            onConfirm={() => handleDeleteKb(record.id)}
            okText={t("common.confirm")}
            cancelText={t("common.cancel")}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </div>
      ),
    },
  ];

  const docColumns = [
    {
      title: t("knowledge.filename"),
      dataIndex: "filename",
      key: "filename",
      ellipsis: true,
    },
    {
      title: t("knowledge.fileType"),
      dataIndex: "file_type",
      key: "file_type",
      width: 100,
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: t("knowledge.chunkCount"),
      dataIndex: "chunk_count",
      key: "chunk_count",
      width: 100,
    },
    {
      title: t("knowledge.actions"),
      key: "actions",
      width: 150,
      render: (_: unknown, record: Document) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="link"
            size="small"
            onClick={() => handlePreviewChunks(record.doc_id)}
            icon={<FileTextOutlined />}
          >
            预览
          </Button>
          <Popconfirm
            title={t("knowledge.deleteDocConfirm")}
            onConfirm={() => handleDeleteDoc(record.doc_id)}
            okText={t("common.confirm")}
            cancelText={t("common.cancel")}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </div>
      ),
    },
  ];

  const searchColumns = [
    {
      title: t("knowledge.document"),
      dataIndex: "filename",
      key: "filename",
      ellipsis: true,
    },
    {
      title: t("knowledge.content"),
      dataIndex: "content",
      key: "content",
      ellipsis: true,
    },
    {
      title: t("knowledge.score"),
      dataIndex: "score",
      key: "score",
      width: 100,
      render: (score: number) => score?.toFixed(4) || "-",
    },
  ];

  return (
    <div className={styles.knowledgePage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{t("knowledge.title")}</h1>
          <p className={styles.description}>{t("knowledge.knowledgeBaseList")}</p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalOpen(true)}
        >
          {t("knowledge.create")}
        </Button>
      </div>

      <div className={styles.layout}>
        {/* Left sidebar - Knowledge base list */}
        <div className={styles.sidebar}>
          <Table
            columns={kbColumns}
            dataSource={knowledgeBases}
            rowKey="id"
            size="small"
            pagination={false}
            onRow={(record) => ({
              onClick: () => handleSelectKb(record.id),
              style: {
                cursor: "pointer",
                background: selectedKbId === record.id ? "#e6f4ff" : "transparent",
              },
            })}
          />
        </div>

        {/* Right content - Knowledge base detail */}
        <div className={styles.content}>
          {!selectedKb ? (
            <div className={styles.emptyState}>
              <p>{t("knowledge.selectKb")}</p>
            </div>
          ) : (
            <>
              <div className={styles.kbHeader}>
                <div>
                  <h2>{selectedKb.name}</h2>
                  <p>{selectedKb.description}</p>
                </div>
              </div>

              <Tabs
                activeKey={activeTab}
                onChange={setActiveTab}
                items={[
                  {
                    key: "documents",
                    label: t("knowledge.documents"),
                    children: (
                      <div className={styles.documentsList}>
                        <div className={styles.toolbar}>
                          <Upload
                            fileList={uploadFiles}
                            onChange={({ fileList }) => setUploadFiles(fileList)}
                            beforeUpload={() => false}
                            multiple
                          >
                            <Button icon={<UploadOutlined />}>
                              {t("knowledge.selectFiles")}
                            </Button>
                          </Upload>
                        </div>

                        {/* Chunk configuration for upload */}
                        <div className={styles.chunkConfig}>
                          <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                            <div>
                              <label style={{ fontSize: 12, color: "#666", marginRight: 8 }}>分块策略</label>
                              <Select
                                value={uploadChunkType}
                                onChange={setUploadChunkType}
                                style={{ width: 150 }}
                                size="small"
                                options={[
                                  { label: "固定长度", value: "length" },
                                  { label: "分隔符", value: "separator" },
                                  { label: "智能分块 (TF-IDF)", value: "tfidf" },
                                ]}
                              />
                            </div>
                            <div>
                              <label style={{ fontSize: 12, color: "#666", marginRight: 8 }}>最大长度</label>
                              <Input
                                type="number"
                                value={uploadMaxLength}
                                onChange={(e) => setUploadMaxLength(Number(e.target.value))}
                                style={{ width: 100 }}
                                size="small"
                                min={100}
                                max={2000}
                              />
                            </div>
                            <div>
                              <label style={{ fontSize: 12, color: "#666", marginRight: 8 }}>重叠长度</label>
                              <Input
                                type="number"
                                value={uploadOverlap}
                                onChange={(e) => setUploadOverlap(Number(e.target.value))}
                                style={{ width: 100 }}
                                size="small"
                                min={0}
                                max={500}
                              />
                            </div>
                            <Button
                              type="primary"
                              onClick={handleUpload}
                              loading={uploading}
                              disabled={uploadFiles.length === 0}
                              size="small"
                            >
                              {t("knowledge.upload")}
                            </Button>
                          </div>
                        </div>

                        <Table
                          columns={docColumns}
                          dataSource={selectedKb.documents}
                          rowKey="doc_id"
                          size="small"
                          pagination={{ pageSize: 10 }}
                        />
                      </div>
                    ),
                  },
                  {
                    key: "search",
                    label: t("knowledge.search"),
                    children: (
                      <div className={styles.searchResults}>
                        <div className={styles.searchBar}>
                          <Input.Search
                            placeholder={t("knowledge.searchPlaceholder")}
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onSearch={handleSearch}
                            loading={searching}
                            enterButton
                          />
                        </div>

                        <Table
                          columns={searchColumns}
                          dataSource={searchResults}
                          rowKey={(record) => record.chunk_id}
                          size="small"
                          pagination={{
                            current: searchPage,
                            pageSize: searchPageSize,
                            showSizeChanger: true,
                            showTotal: (total) => `共 ${total} 条`,
                            pageSizeOptions: ["5", "10", "20", "50"],
                            onChange: (page, pageSize) => {
                              setSearchPage(page);
                              setSearchPageSize(pageSize);
                            },
                          }}
                        />
                      </div>
                    ),
                  },
                ]}
              />
            </>
          )}
        </div>
      </div>

      {/* Create KB Modal */}
      <Modal
        title={t("knowledge.createKb")}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        onOk={handleCreateKb}
        okText={t("common.create")}
        cancelText={t("common.cancel")}
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 500 }}>{t("knowledge.name")} *</label>
          <Input
            value={newKbName}
            onChange={(e) => setNewKbName(e.target.value)}
            placeholder={t("knowledge.namePlaceholder")}
            style={{ marginTop: 8 }}
          />
        </div>
        <div>
          <label style={{ fontSize: 13, fontWeight: 500 }}>{t("knowledge.description")}</label>
          <Input.TextArea
            value={newKbDesc}
            onChange={(e) => setNewKbDesc(e.target.value)}
            placeholder={t("knowledge.descPlaceholder")}
            rows={3}
            style={{ marginTop: 8 }}
          />
        </div>
      </Modal>

      {/* Chunks Preview & Edit Modal */}
      <Modal
        title={t("knowledge.chunkPreview")}
        open={previewModalOpen}
        onCancel={() => setPreviewModalOpen(false)}
        footer={null}
        width={900}
      >
        {/* Reindexing status notification */}
        {reindexingStatus && (
          <div style={{
            marginBottom: 16,
            padding: 12,
            background: "#f0f5ff",
            border: "1px solid #adc6ff",
            borderRadius: 6,
            fontSize: 13,
            color: "#1890ff"
          }}>
            {reindexingStatus}
          </div>
        )}

        {/* Add chunk button at top */}
        <div style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddChunkModalOpen(true)}
          >
            新增块
          </Button>
        </div>

        <div className={styles.chunksList}>
          {editingChunks
            .slice((previewPage - 1) * previewPageSize, previewPage * previewPageSize)
            .map((chunk, index) => {
              const actualIndex = (previewPage - 1) * previewPageSize + index;
              return (
                <div key={chunk.chunk_id} className={styles.chunkItem}>
                  <div className={styles.chunkHeader}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Tag>块 {actualIndex + 1}</Tag>
                      <span className={styles.chunkId}>{chunk.chunk_id}</span>
                    </div>
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleDeleteChunk(chunk.chunk_id)}
                    >
                      删除
                    </Button>
                  </div>
                  <Input.TextArea
                    value={chunk.content}
                    onChange={(e) => {
                      const newChunks = [...editingChunks];
                      newChunks[actualIndex].content = e.target.value;
                      setEditingChunks(newChunks);
                    }}
                    autoSize={{ minRows: 2, maxRows: 10 }}
                    className={styles.chunkContent}
                    style={{ marginTop: 8 }}
                  />
                </div>
              );
            })}
        </div>

        {/* Pagination */}
        {editingChunks.length > previewPageSize && (
          <div style={{ marginTop: 16, display: "flex", justifyContent: "center", alignItems: "center", gap: 12 }}>
            <Button
              size="small"
              disabled={previewPage === 1}
              onClick={() => setPreviewPage(previewPage - 1)}
            >
              上一页
            </Button>
            <span style={{ fontSize: 13, color: "#666" }}>
              第 <strong>{previewPage}</strong> / <strong>{Math.ceil(editingChunks.length / previewPageSize)}</strong> 页
              （共 <strong>{editingChunks.length}</strong> 个块）
            </span>
            <Button
              size="small"
              disabled={previewPage >= Math.ceil(editingChunks.length / previewPageSize)}
              onClick={() => setPreviewPage(previewPage + 1)}
            >
              下一页
            </Button>
            <Input
              type="number"
              size="small"
              style={{ width: 60 }}
              min={1}
              max={Math.ceil(editingChunks.length / previewPageSize)}
              placeholder="页码"
              onPressEnter={(e) => {
                const page = Number((e.target as HTMLInputElement).value);
                if (page >= 1 && page <= Math.ceil(editingChunks.length / previewPageSize)) {
                  setPreviewPage(page);
                }
              }}
            />
            <Button
              size="small"
              onClick={() => {
                const input = document.querySelector(`.${styles.chunksList} input[type="number"]`) as HTMLInputElement;
                const page = Number(input?.value);
                if (page >= 1 && page <= Math.ceil(editingChunks.length / previewPageSize)) {
                  setPreviewPage(page);
                }
              }}
            >
              跳转
            </Button>
          </div>
        )}

        <div style={{ marginTop: 16, textAlign: "right", borderTop: "1px solid #e8e8e8", paddingTop: 12 }}>
          <Button onClick={() => setPreviewModalOpen(false)} style={{ marginRight: 8 }}>
            关闭
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveChunks}
            loading={savingChunks}
          >
            保存并更新索引
          </Button>
        </div>
      </Modal>

      {/* Add Chunk Modal */}
      <Modal
        title="新增块"
        open={addChunkModalOpen}
        onCancel={() => {
          setAddChunkModalOpen(false);
          setNewChunkContent("");
        }}
        onOk={handleAddChunk}
        okText="添加"
        cancelText="取消"
        width={700}
      >
        <Input.TextArea
          value={newChunkContent}
          onChange={(e) => setNewChunkContent(e.target.value)}
          placeholder="输入新块内容..."
          autoSize={{ minRows: 10, maxRows: 20 }}
          style={{ fontSize: 13, lineHeight: 1.6 }}
        />
        <div style={{ marginTop: 8, fontSize: 12, color: "#999" }}>
          提示：添加后会自动跳转到最后一页，记得点击"保存并更新索引"按钮
        </div>
      </Modal>
    </div>
  );
}
