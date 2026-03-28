import { Drawer, Tabs, Button, Upload, Input, Table, Tag, message, Modal, Card, Popconfirm, Select } from "@agentscope-ai/design";
import { useState, useEffect, useCallback, useRef } from "react";
import { PlusOutlined, DeleteOutlined, UploadOutlined, FileTextOutlined, SaveOutlined, SearchOutlined, ReloadOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd";
import { knowledgeApi, type KnowledgeBaseDetail, type Document, type Chunk, type SearchResult } from "../../../../api/modules/knowledge";

interface Props {
  open: boolean;
  kbId: string | null;
  kb: KnowledgeBaseDetail | null;
  onClose: () => void;
  onUpdate: () => void;
}

function getDocumentSuffix(filename?: string, fileType?: string) {
  const normalizedFilename = (filename || "").trim();
  const lastDotIndex = normalizedFilename.lastIndexOf(".");
  if (lastDotIndex > -1 && lastDotIndex < normalizedFilename.length - 1) {
    return normalizedFilename.slice(lastDotIndex + 1).toLowerCase();
  }

  const normalizedFileType = (fileType || "").trim().replace(/^\./, "");
  return normalizedFileType || "-";
}

export function KnowledgeDetailDrawer({ open, kbId, kb, onClose, onUpdate }: Props) {
  const [uploadChunkType, setUploadChunkType] = useState<"length" | "separator" | "tfidf">("length");
  const [uploadMaxLength, setUploadMaxLength] = useState(500);
  const [uploadOverlap, setUploadOverlap] = useState(50);
  const [uploadSeparators, setUploadSeparators] = useState("\\n\\n,\\n,。,.,!,?,;,，,,, ");
  const [uploadFiles, setUploadFiles] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState("documents");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [editingChunks, setEditingChunks] = useState<Chunk[]>([]);
  const [newChunkContent, setNewChunkContent] = useState("");
  const [savingChunks, setSavingChunks] = useState(false);
  const [currentPreviewDocId, setCurrentPreviewDocId] = useState<string | null>(null);
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPageSize] = useState(10);
  const [addChunkModalOpen, setAddChunkModalOpen] = useState(false);
  const [searchPage, setSearchPage] = useState(1);
  const searchPageSize = 10;
  const [reindexingDocIds, setReindexingDocIds] = useState<Set<string>>(new Set());
  const indexingDocsMapRef = useRef<Record<string, boolean>>({});

  // Poll document indexing status
  const pollIndexingStatus = useCallback(async (docIds: string[]) => {
    if (!kbId || docIds.length === 0) return;

    try {
      const statuses = await Promise.all(
        docIds.map(docId =>
          knowledgeApi.getDocumentStatus(kbId!, docId)
        )
      );

      const newStatuses: Record<string, boolean> = {};
      let allCompleted = true;
      let hasChanges = false;

      statuses.forEach((status, idx) => {
        const docId = docIds[idx];
        const isCompleted = status.indexing_status === "completed" || status.indexing_status === "failed";
        newStatuses[docId] = isCompleted;

        if (!isCompleted) {
          allCompleted = false;
        }

        const oldStatus = indexingDocsMapRef.current[docId];
        if (oldStatus !== isCompleted) {
          hasChanges = true;
        }
      });

      if (
        hasChanges ||
        Object.keys(indexingDocsMapRef.current).length !==
          Object.keys(newStatuses).length
      ) {
        indexingDocsMapRef.current = newStatuses;
        if (hasChanges) {
          onUpdate();
        }
      }

      if (!allCompleted) {
        window.setTimeout(() => {
          void pollIndexingStatus(docIds);
        }, 3000);
      }
    } catch (error) {
      console.error("Failed to poll indexing status:", error);
    }
  }, [kbId, onUpdate]);

  // Start polling when kb changes
  useEffect(() => {
    if (kb && kb.documents) {
      const pendingDocIds = kb.documents
        .filter(doc => doc.indexing_status === "pending" || doc.indexing_status === "processing")
        .map(doc => doc.doc_id);

      if (pendingDocIds.length > 0) {
        void pollIndexingStatus(pendingDocIds);
      }
    }
  }, [kb, pollIndexingStatus]);

  const handleUpload = async () => {
    if (!kbId || uploadFiles.length === 0) {
      return;
    }

    setUploading(true);
    try {
      const uploadedDocIds: string[] = [];

      // Parse separators string to array
      const separatorArray = uploadSeparators.split(',').map(s => {
        // Unescape common escape sequences
        return s
          .replace(/\\n/g, '\n')
          .replace(/\\t/g, '\t')
          .replace(/\\r/g, '\r')
          .trim();
      }).filter(s => s.length > 0);

      for (const file of uploadFiles) {
        const fileObj = file.originFileObj;
        if (fileObj) {
          const result = await knowledgeApi.uploadDocument(
            kbId,
            fileObj,
            {
              chunk_type: uploadChunkType,
              max_length: uploadMaxLength,
              overlap: uploadOverlap,
              separators: separatorArray,
            }
          );
          uploadedDocIds.push(result.doc_id);
        }
      }

      message.success(`成功上传 ${uploadFiles.length} 个文件`);
      setUploadFiles([]);
      onUpdate();

      // Poll for indexing status
      if (uploadedDocIds.length > 0) {
        pollIndexingStatus(uploadedDocIds);
      }
    } catch {
      message.error("上传失败");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    if (!kbId) return;

    try {
      await knowledgeApi.deleteDocument(kbId, docId);
      message.success("文档已删除");
      onUpdate();
    } catch {
      message.error("删除失败");
    }
  };

  const handleReindexDocument = async (docId: string) => {
    if (!kbId) return;

    setReindexingDocIds(prev => new Set(prev).add(docId));
    try {
      await knowledgeApi.reindexDocument(kbId, docId);
      message.success("文档重新索引已启动");

      // Start polling for this document
      pollIndexingStatus([docId]);
    } catch {
      message.error("重新索引失败");
      setReindexingDocIds(prev => {
        const next = new Set(prev);
        next.delete(docId);
        return next;
      });
    }
  };

  const handlePreviewChunks = async (docId: string) => {
    if (!kbId) return;

    try {
      const res = await knowledgeApi.getChunks(kbId, docId);
      setEditingChunks(res.chunks || []);
      setCurrentPreviewDocId(docId);
      setPreviewModalOpen(true);
      setPreviewPage(1);
    } catch {
      message.error("加载分块失败");
    }
  };

  const handleSaveChunks = async () => {
    if (!kbId || !currentPreviewDocId) return;

    setSavingChunks(true);
    try {
      await knowledgeApi.saveChunks(kbId, currentPreviewDocId);
      message.success("分块已保存并重新生成向量");
      setPreviewModalOpen(false);
      onUpdate();
    } catch {
      message.error("保存失败");
    } finally {
      setSavingChunks(false);
    }
  };

  const handleAddChunk = async () => {
    if (!kbId || !currentPreviewDocId || !newChunkContent.trim()) {
      return;
    }

    try {
      await knowledgeApi.addChunk(kbId, currentPreviewDocId, newChunkContent);
      message.success("分块已添加");
      setNewChunkContent("");
      // Reload chunks
      const res = await knowledgeApi.getChunks(kbId, currentPreviewDocId);
      setEditingChunks(res.chunks || []);
    } catch {
      message.error("添加失败");
    }
  };

  const handleDeleteChunk = async (chunkId: string) => {
    if (!kbId || !currentPreviewDocId) return;

    try {
      await knowledgeApi.deleteChunk(kbId, currentPreviewDocId, chunkId);
      message.success("分块已删除");
      // Reload chunks
      const res = await knowledgeApi.getChunks(kbId, currentPreviewDocId);
      setEditingChunks(res.chunks || []);
    } catch {
      message.error("删除失败");
    }
  };

  const handleSearch = async () => {
    if (!kbId || !searchQuery.trim()) {
      return;
    }

    setSearching(true);
    try {
      const res = await knowledgeApi.search(kbId, searchQuery, 10);
      setSearchResults(res.results || []);
      setSearchPage(1);
    } catch {
      message.error("检索失败");
    } finally {
      setSearching(false);
    }
  };

  const docColumns = [
    {
      title: "文件名",
      dataIndex: "filename",
      key: "filename",
      ellipsis: true,
    },
    {
      title: "文件类型",
      dataIndex: "file_type",
      key: "file_type",
      width: 100,
      render: (type: string, record: Document) => (
        <Tag>{getDocumentSuffix(record.filename, type)}</Tag>
      ),
    },
    {
      title: "索引状态",
      dataIndex: "indexing_status",
      key: "indexing_status",
      width: 120,
      render: (status: string | undefined, record: Document) => {
        const getStatusColor = (s: string | undefined) => {
          switch (s) {
            case "pending": return "default";
            case "processing": return "processing";
            case "completed": return "success";
            case "failed": return "error";
            default: return "default";
          }
        };

        const getStatusText = (s: string | undefined) => {
          switch (s) {
            case "pending": return "等待中";
            case "processing": return "索引中";
            case "completed": return "已完成";
            case "failed": return "失败";
            default: return "未知";
          }
        };

        const tag = <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>;

        // Show error message for failed status
        if (status === "failed") {
          if (record.indexing_error) {
            return (
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                {tag}
                <span style={{ fontSize: 12, color: "#ff4d4f", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={record.indexing_error}>
                  {record.indexing_error}
                </span>
              </div>
            );
          }
          return tag;
        }

        return tag;
      },
    },
    {
      title: "分块数",
      dataIndex: "chunk_count",
      key: "chunk_count",
      width: 100,
    },
    {
      title: "操作",
      key: "actions",
      width: 280,
      render: (_: unknown, record: Document) => (
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="link"
            size="small"
            icon={<FileTextOutlined />}
            onClick={() => handlePreviewChunks(record.doc_id)}
            disabled={record.chunk_count === 0}
          >
            查看分块
          </Button>
          <Button
            type="link"
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => handleReindexDocument(record.doc_id)}
            loading={reindexingDocIds.has(record.doc_id) || record.indexing_status === "processing"}
            disabled={record.indexing_status === "processing"}
          >
            重新索引
          </Button>
          <Popconfirm
            title="确认删除"
            description="确定要删除这个文档吗？"
            onConfirm={() => handleDeleteDocument(record.doc_id)}
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

  const chunkColumns = [
    {
      title: "序号",
      dataIndex: "chunk_index",
      key: "chunk_index",
      width: 80,
    },
    {
      title: "内容",
      dataIndex: "content",
      key: "content",
      ellipsis: true,
    },
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_: unknown, record: Chunk) => (
        <Popconfirm
          title="确认删除"
          description="确定要删除这个分块吗？"
          onConfirm={() => handleDeleteChunk(record.chunk_id)}
          okText="确定"
          cancelText="取消"
        >
          <Button
            type="link"
            size="small"
            danger
          >
            删除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  const renderDocumentsTab = () => (
    <div>
      <Card title="上传文档" size="small" style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 16 }}>
          <label style={{ marginRight: 8 }}>分块策略:</label>
          <Select
            value={uploadChunkType}
            onChange={setUploadChunkType}
            style={{ width: 150, marginRight: 16 }}
          >
            <Select.Option value="length">固定长度</Select.Option>
            <Select.Option value="separator">分隔符</Select.Option>
            <Select.Option value="tfidf">智能分块</Select.Option>
          </Select>

          <label style={{ marginRight: 8 }}>最大长度:</label>
          <Input
            type="number"
            value={uploadMaxLength}
            onChange={(e) => setUploadMaxLength(Number(e.target.value))}
            style={{ width: 100, marginRight: 16 }}
          />

          <label style={{ marginRight: 8 }}>重叠:</label>
          <Input
            type="number"
            value={uploadOverlap}
            onChange={(e) => setUploadOverlap(Number(e.target.value))}
            style={{ width: 100 }}
          />
        </div>

        {uploadChunkType === "separator" && (
          <div style={{ marginBottom: 16 }}>
            <label style={{ marginRight: 8 }}>分隔符:</label>
            <Input
              value={uploadSeparators}
              onChange={(e) => setUploadSeparators(e.target.value)}
              placeholder="用逗号分隔，如: \\n\\n,\\n,。,.,!,?"
              style={{ width: 400 }}
            />
            <span style={{ marginLeft: 8, fontSize: 12, color: '#999' }}>
              使用逗号分隔多个分隔符，支持 \\n (换行)、\\t (制表符) 等
            </span>
          </div>
        )}

        <Upload
          fileList={uploadFiles}
          onChange={({ fileList }) => setUploadFiles(fileList)}
          beforeUpload={() => false}
          multiple
        >
          <Button icon={<UploadOutlined />}>选择文件</Button>
        </Upload>

        <div style={{ marginTop: 16 }}>
          <Button
            type="primary"
            onClick={handleUpload}
            loading={uploading}
            disabled={uploadFiles.length === 0}
          >
            上传并索引
          </Button>
        </div>
      </Card>

      <div style={{ marginBottom: 12, fontSize: 16, fontWeight: 600 }}>
        已上传文档
      </div>
      <Table
        columns={docColumns}
        dataSource={kb?.documents || []}
        rowKey="doc_id"
        pagination={{ pageSize: 10 }}
      />
    </div>
  );

  const renderSearchTab = () => (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="输入检索内容..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onSearch={handleSearch}
          loading={searching}
          enterButton={<Button type="primary" icon={<SearchOutlined />}>检索</Button>}
        />
      </Card>

      <div style={{ marginBottom: 12, fontSize: 16, fontWeight: 600 }}>
        检索结果
      </div>
      <Table
        columns={searchColumns}
        dataSource={searchResults}
        rowKey={(record) => record.chunk_id}
        pagination={{
          current: searchPage,
          pageSize: searchPageSize,
          total: searchResults.length,
          onChange: (page) => setSearchPage(page),
        }}
      />
    </div>
  );

  return (
    <Drawer
      title={`知识库详情 - ${kb?.name || ""}`}
      onClose={onClose}
      open={open}
      width={900}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: "documents", label: "文档管理", children: renderDocumentsTab() },
          { key: "search", label: "检索", children: renderSearchTab() },
        ]}
      />

      <Modal
        title="编辑分块"
        open={previewModalOpen}
        onCancel={() => {
          setPreviewModalOpen(false);
          setEditingChunks([]);
          setCurrentPreviewDocId(null);
        }}
        width={800}
        footer={[
          <Button key="cancel" onClick={() => setPreviewModalOpen(false)}>
            取消
          </Button>,
          <Button
            key="add"
            icon={<PlusOutlined />}
            onClick={() => setAddChunkModalOpen(true)}
          >
            添加分块
          </Button>,
          <Button
            key="save"
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSaveChunks}
            loading={savingChunks}
          >
            保存并重新索引
          </Button>,
        ]}
      >
        <Table
          columns={chunkColumns}
          dataSource={editingChunks}
          rowKey="chunk_id"
          pagination={{
            current: previewPage,
            pageSize: previewPageSize,
            total: editingChunks.length,
            onChange: (page) => setPreviewPage(page),
          }}
          expandable={{
            expandedRowRender: (record) => (
              <div style={{ padding: 16 }}>
                <Input.TextArea
                  value={record.content}
                  onChange={(e) => {
                    const newChunks = editingChunks.map(c =>
                      c.chunk_id === record.chunk_id
                        ? { ...c, content: e.target.value }
                        : c
                    );
                    setEditingChunks(newChunks);
                  }}
                  rows={6}
                />
              </div>
            ),
          }}
        />
      </Modal>

      <Modal
        title="添加分块"
        open={addChunkModalOpen}
        onOk={handleAddChunk}
        onCancel={() => {
          setAddChunkModalOpen(false);
          setNewChunkContent("");
        }}
      >
        <Input.TextArea
          placeholder="输入新分块的内容..."
          value={newChunkContent}
          onChange={(e) => setNewChunkContent(e.target.value)}
          rows={6}
        />
      </Modal>
    </Drawer>
  );
}
