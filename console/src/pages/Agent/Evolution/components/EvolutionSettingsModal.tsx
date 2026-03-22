import { Modal, InputNumber, message } from "@agentscope-ai/design";
import { Form, Switch } from "antd";
import { useEffect, useState } from "react";
import { evolutionApi } from "../../../../api/modules/evolution";
import type { EvolutionConfig } from "../../../../api/types/evolution";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfigSaved?: () => void;
}

export function EvolutionSettingsModal({
  open,
  onClose,
  onConfigSaved,
}: Props) {
  const [form] = Form.useForm<EvolutionConfig>();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      loadConfig();
    }
  }, [open]);

  const loadConfig = async () => {
    try {
      const config = await evolutionApi.getConfig();
      form.setFieldsValue(config);
    } catch (error) {
      message.error("加载配置失败");
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      await evolutionApi.updateConfig(values);
      message.success("配置已保存");
      onConfigSaved?.();
      onClose();
    } catch (error) {
      message.error("保存配置失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="进化设置"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={loading}
      width={600}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          label="启用进化功能"
          name="enabled"
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Form.Item
          label="启用自动进化"
          name="auto_evolution"
          valuePropName="checked"
          tooltip="开启后会创建默认定时任务（每日12:00），可在定时任务页面修改"
        >
          <Switch />
        </Form.Item>

        <Form.Item noStyle shouldUpdate={(prev, cur) => prev.auto_evolution !== cur.auto_evolution}>
          {({ getFieldValue }) => {
            const autoEvolution = getFieldValue("auto_evolution");
            return autoEvolution ? (
              <div style={{ marginBottom: 24, padding: 12, background: "#f0f5ff", borderRadius: 4 }}>
                <div style={{ fontSize: 12, color: "#1890ff", marginBottom: 4 }}>
                  ℹ️ 已创建默认定时任务
                </div>
                <div style={{ fontSize: 12, color: "#666" }}>
                  开启自动进化后，系统会创建一个定时任务（每日12:00执行）。
                  您可以前往 <strong>定时任务</strong> 页面调整执行时间或频率。
                </div>
              </div>
            ) : null;
          }}
        </Form.Item>

        <Form.Item
          label="最大代数"
          name="max_generations"
          tooltip="智能体进化的最大代数限制，留空或0表示无限进化"
        >
          <InputNumber
            min={0}
            max={10000}
            placeholder="无限"
            style={{ width: "100%" }}
          />
        </Form.Item>

        <Form.Item
          label="启用存档"
          name="archive_enabled"
          valuePropName="checked"
          tooltip="是否保存每轮进化的完整快照"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}
