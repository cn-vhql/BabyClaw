import type { ProviderInfo } from "../../../../../api/types";
import { lazy, Suspense } from "react";
import { Modal } from "@agentscope-ai/design";
import { useTranslation } from "react-i18next";
import { isOnlineOnlyMode } from "../../../../../api/config";
import styles from "../../index.module.less";

const LocalModelManageModal = isOnlineOnlyMode
  ? null
  : lazy(() =>
      import("./LocalModelManageModal").then((module) => ({
        default: module.LocalModelManageModal,
      })),
    );
const OllamaModelManageModal = isOnlineOnlyMode
  ? null
  : lazy(() =>
      import("./OllamaModelManageModal").then((module) => ({
        default: module.OllamaModelManageModal,
      })),
    );
const RemoteModelManageModal = lazy(() =>
  import("./RemoteModelManageModal").then((module) => ({
    default: module.RemoteModelManageModal,
  })),
);

interface ModelManageModalProps {
  provider: ProviderInfo;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

function ModelManageModalFallback({
  providerName,
  open,
  onClose,
}: {
  providerName: string;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Modal
      title={t("models.manageModelsTitle", { provider: providerName })}
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
    >
      <div className={styles.modalLoading}>{t("common.loading")}</div>
    </Modal>
  );
}

export function ModelManageModal({
  provider,
  open,
  onClose,
  onSaved,
}: ModelManageModalProps) {
  const loadingFallback = (
    <ModelManageModalFallback
      providerName={provider.name}
      open={open}
      onClose={onClose}
    />
  );

  // Route to the appropriate specialized modal based on provider type
  if (!isOnlineOnlyMode && provider.id === "ollama" && OllamaModelManageModal) {
    return (
      <Suspense fallback={loadingFallback}>
        <OllamaModelManageModal
          provider={provider}
          open={open}
          onClose={onClose}
          onSaved={onSaved}
        />
      </Suspense>
    );
  }

  if (!isOnlineOnlyMode && provider.is_local && LocalModelManageModal) {
    return (
      <Suspense fallback={loadingFallback}>
        <LocalModelManageModal
          provider={provider}
          open={open}
          onClose={onClose}
          onSaved={onSaved}
        />
      </Suspense>
    );
  }

  return (
    <Suspense fallback={loadingFallback}>
      <RemoteModelManageModal
        provider={provider}
        open={open}
        onClose={onClose}
        onSaved={onSaved}
      />
    </Suspense>
  );
}
