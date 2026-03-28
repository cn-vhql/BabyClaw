import { useState, useEffect, useRef, useCallback } from "react";
import { Modal, Button, message, Input, Empty } from "@agentscope-ai/design";
import { Tree, Spin, Typography } from "antd";
import type { DataNode, EventDataNode } from "antd/es/tree";
import {
  FileOutlined,
  FolderOutlined,
  DeleteOutlined,
  DownloadOutlined,
  UploadOutlined,
  ReloadOutlined,
  CaretRightFilled,
} from "@ant-design/icons";
import { workspaceApi } from "../../../../api/modules/workspace";
import type { FileTreeNode, FileContentResult } from "../../../../api/types/workspace";
import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

const { Text } = Typography;

interface FileExplorerModalProps {
  open: boolean;
  onClose: () => void;
}

// Preset files and directories that cannot be deleted
const PRESET_FILES = [
  "copaw.db",
  "copaw.db-journal",
  "agent.json",
  // Core markdown files
  "AGENTS.md",
  "SOUL.md",
  "PROFILE.md",
  "MEMORY.md",
  "BOOTSTRAP.md",
  "HEARTBEAT.md",
  // Working and memory directories
  "working_dir",
  "memory",
];

export const FileExplorerModal: React.FC<FileExplorerModalProps> = ({
  open,
  onClose,
}) => {
  const { t } = useTranslation();
  const [fileTree, setFileTree] = useState<FileTreeNode | null>(null);
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [fileContent, setFileContent] = useState<FileContentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [contentLoading, setContentLoading] = useState(false);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getErrorMessage = (error: unknown, fallback: string) => {
    if (
      typeof error === "object" &&
      error !== null &&
      "message" in error &&
      typeof error.message === "string"
    ) {
      return error.message;
    }
    return fallback;
  };

  // Load file tree when modal opens
  const loadFileTree = useCallback(async () => {
    setLoading(true);
    try {
      const tree = await workspaceApi.getFileTree();
      setFileTree(tree);
      // Auto-expand first level
      if (tree.children && tree.children.length > 0) {
        setExpandedKeys(tree.children.map((child) => child.path));
      }
    } catch (error) {
      console.error("Failed to load file tree:", error);
      message.error(t("workspace.loadFileTreeFailed") || "Failed to load file tree");
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (open) {
      void loadFileTree();
    }
  }, [loadFileTree, open]);

  const loadFileContent = async (path: string) => {
    setContentLoading(true);
    try {
      const content = await workspaceApi.getFileContent(path);
      setFileContent(content);
    } catch (error) {
      console.error("Failed to load file content:", error);
      message.error(t("workspace.loadFileContentFailed") || "Failed to load file content");
    } finally {
      setContentLoading(false);
    }
  };

  const handleSelect = (
    selectedKeys: React.Key[],
    info: { node: EventDataNode<DataNode> },
  ) => {
    if (selectedKeys.length > 0) {
      const path = selectedKeys[0] as string;
      setSelectedPath(path);

      // Load content if it's a file
      const node = info.node;
      if (node.isLeaf) {
        loadFileContent(path);
      } else {
        setFileContent(null);
      }
    }
  };

  const handleExpand = (expandedKeys: React.Key[]) => {
    setExpandedKeys(expandedKeys as string[]);
  };

  const handleDelete = async () => {
    if (!selectedPath) return;

    const fileName = selectedPath.split("/").pop() || "";
    if (PRESET_FILES.includes(fileName)) {
      message.error(t("workspace.cannotDeletePreset") || "Cannot delete preset file");
      return;
    }

    Modal.confirm({
      title: t("workspace.deleteConfirm") || "Confirm Delete",
      content: (
        t("workspace.deleteConfirmDesc") ||
        "Are you sure you want to delete this? This action cannot be undone."
      ).replace("{path}", selectedPath),
      onOk: async () => {
        try {
          await workspaceApi.deleteFile(selectedPath);
          message.success(t("workspace.deleteSuccess") || "Deleted successfully");
          loadFileTree();
          setFileContent(null);
          setSelectedPath("");
        } catch (error) {
          console.error("Failed to delete file:", error);
          message.error(
            getErrorMessage(
              error,
              t("workspace.deleteFailed") || "Delete failed",
            ),
          );
        }
      },
    });
  };

  const handleDownload = async () => {
    if (!selectedPath) return;

    try {
      const blob = await workspaceApi.downloadSingleFile(selectedPath);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const fileName = selectedPath.split("/").pop() || "download";
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      message.success(t("workspace.downloadSuccess") || "Downloaded successfully");
    } catch (error) {
      console.error("Download failed:", error);
      message.error(t("workspace.downloadFailed") || "Download failed");
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      // Upload to current selected folder or root
      const targetPath = selectedPath && fileTree?.children?.find(
        (child: FileTreeNode) => child.path === selectedPath && child.type === "folder"
      ) ? selectedPath : "";

      const result = await workspaceApi.uploadSingleFile(file, targetPath);
      message.success(
        (t("workspace.uploadSuccess") || "Uploaded successfully") + `: ${result.filename}`
      );
      loadFileTree();
    } catch (error) {
      console.error("Upload failed:", error);
      message.error(
        getErrorMessage(error, t("workspace.uploadFailed") || "Upload failed"),
      );
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  // Convert tree data to Ant Design Tree format
  const convertToTreeData = (node: FileTreeNode): DataNode => {
    const isLeaf = node.type === "file";
    const isPreset = PRESET_FILES.includes(node.name);

    return {
      title: (
        <span className={styles.treeNode}>
          <span className={styles.nodeName}>{node.name}</span>
          {isPreset && (
            <Text type="secondary" className={styles.presetBadge}>
              ({t("workspace.preset") || "Preset"})
            </Text>
          )}
        </span>
      ),
      key: node.path,
      isLeaf,
      icon: isLeaf ? <FileOutlined /> : <FolderOutlined />,
      children: node.children?.map((child) => convertToTreeData(child)),
      disabled: isPreset,
    };
  };

  const treeData = fileTree ? [convertToTreeData(fileTree)] : [];

  // Check if selected item is a preset file or folder at root level
  const isPresetItem = selectedPath
    ? PRESET_FILES.includes(selectedPath.split("/")[0] || "")
    : false;

  const canDelete = selectedPath && !isPresetItem;
  const canDownload = selectedPath && fileContent !== null;

  return (
    <Modal
      title={t("workspace.fileExplorer") || "File Explorer"}
      open={open}
      onCancel={onClose}
      footer={null}
      width={1100}
      style={{ top: 40 }}
      className={styles.fileExplorerModal}
    >
      <div className={styles.fileExplorerContent}>
        {/* Left panel - File tree */}
        <div className={styles.fileTreePanel}>
          <div className={styles.panelHeader}>
            <Text strong>{t("workspace.files") || "Files"}</Text>
            <Button
              size="small"
              icon={<ReloadOutlined />}
              onClick={loadFileTree}
              loading={loading}
            />
          </div>

          <div className={styles.treeContainer}>
            {loading ? (
              <div className={styles.centerState}>
                <Spin />
              </div>
            ) : treeData.length > 0 ? (
              <Tree
                showIcon
                expandedKeys={expandedKeys}
                selectedKeys={selectedPath ? [selectedPath] : []}
                onExpand={handleExpand}
                onSelect={handleSelect}
                treeData={treeData}
                switcherIcon={<CaretRightFilled />}
              />
            ) : (
              <Empty
                description={t("workspace.noFiles") || "No files"}
                image={undefined}
              />
            )}
          </div>

          <div className={styles.panelActions}>
            <Button
              size="small"
              icon={<UploadOutlined />}
              onClick={handleUploadClick}
            >
              {t("common.upload") || "Upload"}
            </Button>
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              disabled={!canDownload}
            >
              {t("common.download") || "Download"}
            </Button>
            <Button
              size="small"
              icon={<DeleteOutlined />}
              onClick={handleDelete}
              disabled={!canDelete}
              danger
            >
              {t("common.delete") || "Delete"}
            </Button>
          </div>
        </div>

        {/* Right panel - File preview */}
        <div className={styles.filePreviewPanel}>
          <div className={styles.panelHeader}>
            <Text strong>
              {fileContent ? fileContent.name : (t("workspace.preview") || "Preview")}
            </Text>
            {fileContent && (
              <Text type="secondary" className={styles.fileMeta}>
                {(fileContent.size / 1024).toFixed(2)} KB
              </Text>
            )}
          </div>

          <div className={styles.previewContainer}>
            {contentLoading ? (
              <div className={styles.centerState}>
                <Spin />
              </div>
            ) : fileContent ? (
              fileContent.is_text ? (
                <Input.TextArea
                  value={fileContent.content || ""}
                  readOnly
                  className={styles.previewTextarea}
                  autoSize={{ minRows: 20, maxRows: 20 }}
                />
              ) : (
                <Empty
                  description={t("workspace.binaryFile") || "Binary file - preview not available"}
                  image={undefined}
                />
              )
            ) : (
              <Empty
                description={t("workspace.selectFile") || "Select a file to preview"}
                image={undefined}
              />
            )}
          </div>
        </div>
      </div>

      {/* Hidden file input for upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        style={{ display: "none" }}
      />
    </Modal>
  );
};
