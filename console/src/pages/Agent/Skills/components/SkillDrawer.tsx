import { useState, useEffect, useCallback, useRef } from "react";
import { Drawer, Form, Input, Button, message } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import { ThunderboltOutlined, StopOutlined } from "@ant-design/icons";
import type { FormInstance } from "antd";
import type { SkillSpec } from "../../../../api/types";
import { MarkdownCopy } from "../../../../components/MarkdownCopy/MarkdownCopy";
import { api } from "../../../../api";

/**
 * Parse frontmatter from content string.
 * Returns an object with parsed key-value pairs, or null if no valid frontmatter found.
 */
function parseFrontmatter(content: string): Record<string, string> | null {
  const trimmed = content.trim();
  if (!trimmed.startsWith("---")) return null;

  const endIndex = trimmed.indexOf("---", 3);
  if (endIndex === -1) return null;

  const frontmatterBlock = trimmed.slice(3, endIndex).trim();
  if (!frontmatterBlock) return null;

  const result: Record<string, string> = {};
  for (const line of frontmatterBlock.split("\n")) {
    const colonIndex = line.indexOf(":");
    if (colonIndex > 0) {
      const key = line.slice(0, colonIndex).trim();
      const value = line.slice(colonIndex + 1).trim();
      result[key] = value;
    }
  }
  return result;
}

/**
 * Remove frontmatter from content, return only the markdown content.
 */
function removeFrontmatter(content: string): string {
  const trimmed = content.trim();
  if (!trimmed.startsWith("---")) return content;

  const endIndex = trimmed.indexOf("---", 3);
  if (endIndex === -1) return content;

  return trimmed.slice(endIndex + 3).trim();
}

/**
 * Build skill file content from name, description and content.
 */
function buildSkillContent(name: string, description: string, content: string): string {
  const cleanContent = content.trim();
  const escapedDescription = description.replace(/"/g, '\\"');
  return `---
name: ${name}
description: "${escapedDescription}"
---

${cleanContent}`;
}

interface SkillDrawerProps {
  open: boolean;
  editingSkill: SkillSpec | null;
  form: FormInstance<SkillSpec>;
  onClose: () => void;
  onSubmit: (values: { name: string; description: string; content: string }) => void;
  onContentChange?: (content: string) => void;
}

export function SkillDrawer({
  open,
  editingSkill,
  form,
  onClose,
  onSubmit,
  onContentChange,
}: SkillDrawerProps) {
  const { t, i18n } = useTranslation();
  const [showMarkdown, setShowMarkdown] = useState(true);
  const [contentValue, setContentValue] = useState("");
  const [optimizing, setOptimizing] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const validateContent = useCallback(
    (_: unknown, value: string) => {
      const contentToCheck = value || contentValue;
      if (!contentToCheck || !contentToCheck.trim()) {
        return Promise.reject(new Error(t("skills.pleaseInputContent")));
      }
      return Promise.resolve();
    },
    [contentValue, t],
  );

  useEffect(() => {
    if (editingSkill) {
      // Parse frontmatter to extract name and description
      const fm = parseFrontmatter(editingSkill.content);
      const contentWithoutFrontmatter = removeFrontmatter(editingSkill.content);

      form.setFieldsValue({
        name: editingSkill.name,
        description: fm?.description || "",
        content: contentWithoutFrontmatter,
      });
      setContentValue(contentWithoutFrontmatter);
    } else {
      form.resetFields();
      setContentValue("");
    }
  }, [editingSkill, form]);

  const handleSubmit = (values: { name: string; description: string; content: string }) => {
    const { name, description, content } = values;
    const finalContent = buildSkillContent(name, description, contentValue || content);

    if (editingSkill) {
      // Edit mode: submit with the editing skill's name
      onSubmit({
        name: editingSkill.name,
        description,
        content: finalContent,
      });
    } else {
      // Create mode
      onSubmit({
        name,
        description,
        content: finalContent,
      });
    }
  };

  const handleContentChange = (content: string) => {
    setContentValue(content);
    form.setFieldsValue({ content });
    form.validateFields(["content"]).catch(() => {});
    if (onContentChange) {
      onContentChange(content);
    }
  };

  const handleOptimize = async () => {
    if (!contentValue.trim()) {
      message.warning(t("skills.noContentToOptimize"));
      return;
    }

    setOptimizing(true);
    abortControllerRef.current = new AbortController();
    const originalContent = contentValue;
    setContentValue(""); // Clear content for streaming output

    try {
      await api.streamOptimizeSkill(
        originalContent,
        (textChunk) => {
          setContentValue((prev) => {
            const newContent = prev + textChunk;
            form.setFieldsValue({ content: newContent });
            return newContent;
          });
        },
        abortControllerRef.current.signal,
        i18n.language, // Pass current language to API
      );
      message.success(t("skills.optimizeSuccess"));
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        message.error(error instanceof Error ? error.message : t("skills.optimizeFailed"));
      }
    } finally {
      setOptimizing(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopOptimize = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setOptimizing(false);
      abortControllerRef.current = null;
    }
  };

  const drawerFooter = (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        width: "100%",
      }}
    >
      <div>
        {!editingSkill && (
          <>
            {!optimizing ? (
              <Button
                type="default"
                icon={<ThunderboltOutlined />}
                onClick={handleOptimize}
                disabled={!contentValue.trim()}
              >
                {t("skills.optimizeWithAI")}
              </Button>
            ) : (
              <Button
                type="default"
                danger
                icon={<StopOutlined />}
                onClick={handleStopOptimize}
              >
                {t("skills.stopOptimize")}
              </Button>
            )}
          </>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button type="primary" onClick={() => form.submit()}>
          {editingSkill ? t("skills.update") : t("skills.create")}
        </Button>
      </div>
    </div>
  );

  return (
    <Drawer
      width={520}
      placement="right"
      title={editingSkill ? t("skills.editSkill") : t("skills.createSkill")}
      open={open}
      onClose={onClose}
      destroyOnClose
      footer={drawerFooter}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        {!editingSkill && (
          <>
            <Form.Item
              name="name"
              label="Name"
              rules={[{ required: true, message: t("skills.pleaseInputName") }]}
            >
              <Input placeholder={t("skills.skillNamePlaceholder")} />
            </Form.Item>

            <Form.Item
              name="description"
              label="Description"
              rules={[{ required: true, message: t("skills.pleaseInputDescription") }]}
            >
              <Input.TextArea
                placeholder={t("skills.skillDescriptionPlaceholder")}
                rows={3}
              />
            </Form.Item>

            <Form.Item
              name="content"
              label="Content"
              rules={[{ required: true, validator: validateContent }]}
            >
              <MarkdownCopy
                content={contentValue}
                showMarkdown={showMarkdown}
                onShowMarkdownChange={setShowMarkdown}
                editable={true}
                onContentChange={handleContentChange}
                textareaProps={{
                  placeholder: t("skills.contentPlaceholder"),
                  rows: 12,
                }}
              />
            </Form.Item>
          </>
        )}

        {editingSkill && (
          <>
            <Form.Item name="name" label="Name">
              <Input disabled value={editingSkill.name} />
            </Form.Item>

            <Form.Item
              name="description"
              label="Description"
              rules={[{ required: true, message: t("skills.pleaseInputDescription") }]}
            >
              <Input.TextArea
                placeholder={t("skills.skillDescriptionPlaceholder")}
                rows={3}
              />
            </Form.Item>

            <Form.Item name="content" label="Content" rules={[{ required: true, validator: validateContent }]}>
              <MarkdownCopy
                content={contentValue}
                showMarkdown={showMarkdown}
                onShowMarkdownChange={setShowMarkdown}
                editable={true}
                onContentChange={handleContentChange}
                textareaProps={{
                  placeholder: t("skills.contentPlaceholder"),
                  rows: 12,
                }}
              />
            </Form.Item>

            <Form.Item name="source" label="Source">
              <Input disabled value={editingSkill.source} />
            </Form.Item>

            <Form.Item name="path" label="Path">
              <Input disabled value={editingSkill.path} />
            </Form.Item>
          </>
        )}
      </Form>
    </Drawer>
  );
}
