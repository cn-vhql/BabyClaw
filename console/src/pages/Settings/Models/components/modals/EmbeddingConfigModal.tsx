import { useState, useEffect, useCallback } from "react";
import {
  Form,
  Input,
  Modal,
  message,
  Button,
  Switch,
  InputNumber,
  Select,
} from "@agentscope-ai/design";
import api from "../../../../../api";
import { useTranslation } from "react-i18next";

interface EmbeddingConfigModalProps {
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

interface EmbeddingConfig {
  backend: string;
  api_key: string;
  base_url: string;
  model_name: string;
  dimensions: number;
  enable_cache: boolean;
  use_dimensions: boolean;
  max_cache_size: number;
  max_input_length: number;
  max_batch_size: number;
}

export function EmbeddingConfigModal({
  open,
  onClose,
  onSaved,
}: EmbeddingConfigModalProps) {
  const { t } = useTranslation();
  const [form] = Form.useForm<EmbeddingConfig>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadConfig = useCallback(async () => {
    if (!open) return;

    setLoading(true);
    try {
      const config = await api.getEmbeddingConfig();
      form.setFieldsValue(config);
    } catch (error) {
      message.error(t("models.embedding.loadFailed"));
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [form, open, t]);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      await api.updateEmbeddingConfig(values);
      message.success(t("models.embedding.saveSuccess"));
      onSaved?.();
      onClose();
    } catch (error) {
      message.error(t("models.embedding.saveFailed"));
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={t("models.embedding.title")}
      open={open}
      onCancel={onClose}
      footer={
        <div style={{ textAlign: "right" }}>
          <Button onClick={onClose} style={{ marginRight: 8 }}>
            {t("common.cancel")}
          </Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            {t("common.save")}
          </Button>
        </div>
      }
      width={700}
      styles={{ body: { maxHeight: 500, overflowY: "auto" } }}
    >
      <Form
        form={form}
        layout="vertical"
        disabled={loading}
        initialValues={{
          backend: "openai",
          api_key: "",
          base_url: "",
          model_name: "",
          dimensions: 1024,
          enable_cache: true,
          use_dimensions: false,
          max_cache_size: 2000,
          max_input_length: 8192,
          max_batch_size: 10,
        }}
      >
        <Form.Item
          label={t("models.embedding.backend")}
          name="backend"
          rules={[{ required: true }]}
        >
          <Select>
            <Select.Option value="openai">OpenAI</Select.Option>
            <Select.Option value="ollama">Ollama</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item label={t("models.embedding.apiKey")} name="api_key">
          <Input.Password
            placeholder={t("models.embedding.apiKeyPlaceholder")}
          />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.baseUrl")}
          name="base_url"
          tooltip={t("models.embedding.baseUrlTooltip")}
        >
          <Input placeholder="https://api.openai.com/v1" />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.modelName")}
          name="model_name"
          tooltip={t("models.embedding.modelNameTooltip")}
        >
          <Input placeholder="text-embedding-3-small" />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.dimensions")}
          name="dimensions"
          tooltip={t("models.embedding.dimensionsTooltip")}
        >
          <InputNumber min={1} max={4096} style={{ width: "100%" }} />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.useDimensions")}
          name="use_dimensions"
          valuePropName="checked"
          tooltip={t("models.embedding.useDimensionsTooltip")}
        >
          <Switch />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.enableCache")}
          name="enable_cache"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.maxCacheSize")}
          name="max_cache_size"
        >
          <InputNumber min={0} style={{ width: "100%" }} />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.maxInputLength")}
          name="max_input_length"
        >
          <InputNumber min={1} max={128000} style={{ width: "100%" }} />
        </Form.Item>

        <Form.Item
          label={t("models.embedding.maxBatchSize")}
          name="max_batch_size"
        >
          <InputNumber min={1} max={100} style={{ width: "100%" }} />
        </Form.Item>
      </Form>

      <div
        style={{
          marginTop: 16,
          padding: 12,
          background: "#f5f5f5",
          borderRadius: 8,
        }}
      >
        <div style={{ fontSize: 12, color: "#666", marginBottom: 8 }}>
          {t("models.embedding.noteTitle")}:
        </div>
        <ul style={{ fontSize: 12, color: "#999", margin: 0, paddingLeft: 20 }}>
          <li>{t("models.embedding.noteRequired")}</li>
          <li>{t("models.embedding.noteModels")}</li>
          <li>{t("models.embedding.noteVector")}</li>
        </ul>
      </div>
    </Modal>
  );
}
