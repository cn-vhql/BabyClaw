import {
  AgentScopeRuntimeWebUI,
  ChatInput,
  IAgentScopeRuntimeWebUIOptions,
  type IAgentScopeRuntimeWebUISession,
  type IAgentScopeRuntimeWebUIMessage,
  type IAgentScopeRuntimeWebUIRef,
  Stream,
} from "@agentscope-ai/chat";
import {
  useCallback,
  createContext,
  useEffect,
  useContext,
  memo,
  useMemo,
  useRef,
  startTransition,
  useState,
  type CSSProperties,
} from "react";
import { Button, Input, Modal, Result, message } from "antd";
import {
  CloseOutlined,
  DeleteOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  SaveOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { SparkCopyLine } from "@agentscope-ai/icons";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import sessionApi from "./sessionApi";
import defaultConfig, { getDefaultConfig } from "./OptionsPanel/defaultConfig";
import { chatApi } from "../../api/modules/chat";
import { getApiToken, getApiUrl } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import api from "../../api";
import ModelSelector from "./ModelSelector";
import { useTheme } from "../../contexts/useTheme";
import { useAgentStore } from "../../stores/agentStore";
import AgentScopeRuntimeResponseBuilder from "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/Response/Builder.js";
import {
  AgentScopeRuntimeMessageType,
  AgentScopeRuntimeRunStatus,
} from "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/AgentScopeRuntime/types.js";
import { useChatAnywhereInput } from "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/Context/ChatAnywhereInputContext.js";
import { IconButton, Modal as SparkModal } from "@agentscope-ai/design";
import { SparkAttachmentLine } from "@agentscope-ai/icons";
import ChatThemeSelector from "./ThemeSelector";
import {
  getChatTheme,
  getStoredChatTheme,
  persistChatTheme,
  type ChatThemeKey,
} from "./chatThemes";
import styles from "./index.module.less";

type CopyableContent = {
  type?: string;
  text?: string;
  refusal?: string;
};

type CopyableMessage = {
  role?: string;
  content?: string | CopyableContent[];
};

type CopyableResponse = {
  output?: CopyableMessage[];
};

type RuntimeUiMessage = IAgentScopeRuntimeWebUIMessage & {
  msgStatus?: string;
  role?: string;
  cards?: Array<{
    code: string;
    data: unknown;
  }>;
  history?: boolean;
};

type StreamResponseData = {
  status?: string;
  output?: Array<{
    content?: unknown[];
  }>;
};

type ChatFetchSession = {
  session_id?: string;
  user_id?: string;
  channel?: string;
};

type ChatInputPart = Record<string, unknown> & {
  type?: string;
  image_url?: string;
  file_url?: string;
  audio_url?: string;
  video_url?: string;
};

type ChatInputMessage = Record<string, unknown> & {
  content?: ChatInputPart[];
  session?: ChatFetchSession;
};

type ChatFetchPayload = {
  input?: ChatInputMessage[];
  biz_params?: Record<string, unknown>;
  signal?: AbortSignal;
  reconnect?: boolean;
  session_id?: string;
  user_id?: string;
  channel?: string;
};

type SseChunk = Record<string, string>;

type RuntimeStreamEvent = {
  object?: string;
  id?: string;
  msg_id?: string;
  role?: string;
  type?: string;
  status?: string;
  content?: unknown[];
};

type PendingAssistantMessage = {
  chunk: SseChunk;
  data: RuntimeStreamEvent & {
    id: string;
  };
};

type RuntimeLoadingBridgeApi = {
  getLoading?: () => boolean | string;
  setLoading?: (loading: boolean | string) => void;
};

type ChatThemeContextValue = {
  chatThemeKey: ChatThemeKey;
  setChatThemeKey: (theme: ChatThemeKey) => void;
  isDark: boolean;
};

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

const sseEncoder = new TextEncoder();
const ChatThemeContext = createContext<ChatThemeContextValue | null>(null);

function useChatThemeContext() {
  const context = useContext(ChatThemeContext);
  if (!context) {
    throw new Error("ChatThemeContext is not available");
  }
  return context;
}
const EMPTY_ASSISTANT_PLACEHOLDER = "\u200b";
const QUICK_PROMPTS_STORAGE_KEY = "copaw.chat.quick-prompts.v2";
const LEGACY_QUICK_PROMPTS_STORAGE_KEY = "copaw.chat.quick-prompts.v1";
const DEFAULT_QUICK_PROMPTS = ["保存为新技能", "更新自我认知"];
const MAX_QUICK_PROMPTS = 6;
const RUNTIME_CHAT_THEME = {
  colorPrimary: "#1f5e78",
  colorBgBase: "#f4f9fb",
  colorTextBase: "#173344",
  darkMode: false,
  background: "transparent",
} as const;

function normalizeQuickPrompts(prompts: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];

  prompts.forEach((prompt) => {
    const trimmed = prompt.trim();
    if (!trimmed || seen.has(trimmed)) {
      return;
    }
    seen.add(trimmed);
    result.push(trimmed);
  });

  return result.slice(0, MAX_QUICK_PROMPTS);
}

function getQuickPromptStorageAgentKey(agentId?: string): string {
  const trimmed = agentId?.trim();
  return trimmed || "default";
}

function loadLegacyQuickPrompts(): string[] | null {
  try {
    const raw = window.localStorage.getItem(LEGACY_QUICK_PROMPTS_STORAGE_KEY);
    if (raw === null) {
      return null;
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return null;
    }

    return normalizeQuickPrompts(
      parsed.filter((item): item is string => typeof item === "string"),
    );
  } catch {
    return null;
  }
}

function readQuickPromptsStorage(): Record<string, string[]> {
  try {
    const raw = window.localStorage.getItem(QUICK_PROMPTS_STORAGE_KEY);
    if (raw === null) {
      return {};
    }

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    return Object.fromEntries(
      Object.entries(parsed).map(([key, value]) => [
        key,
        normalizeQuickPrompts(
          Array.isArray(value)
            ? value.filter((item): item is string => typeof item === "string")
            : [],
        ),
      ]),
    );
  } catch {
    return {};
  }
}

function loadQuickPrompts(agentId?: string): string[] {
  if (typeof window === "undefined") {
    return DEFAULT_QUICK_PROMPTS;
  }

  try {
    const agentKey = getQuickPromptStorageAgentKey(agentId);
    const storage = readQuickPromptsStorage();
    if (Object.prototype.hasOwnProperty.call(storage, agentKey)) {
      return storage[agentKey] ?? [];
    }

    const legacyPrompts = loadLegacyQuickPrompts();
    if (legacyPrompts) {
      return legacyPrompts;
    }
  } catch {
    return DEFAULT_QUICK_PROMPTS;
  }

  return DEFAULT_QUICK_PROMPTS;
}

function persistQuickPrompts(agentId: string | undefined, prompts: string[]): void {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const agentKey = getQuickPromptStorageAgentKey(agentId);
    const storage = readQuickPromptsStorage();
    storage[agentKey] = normalizeQuickPrompts(prompts);
    window.localStorage.setItem(
      QUICK_PROMPTS_STORAGE_KEY,
      JSON.stringify(storage),
    );
  } catch {
    // Ignore local persistence failures.
  }
}

function extractCopyableText(response: CopyableResponse): string {
  const collectText = (assistantOnly: boolean) => {
    const chunks = (response.output || []).flatMap((item: CopyableMessage) => {
      if (assistantOnly && item.role !== "assistant") return [];

      if (typeof item.content === "string") {
        return [item.content];
      }

      if (!Array.isArray(item.content)) {
        return [];
      }

      return item.content.flatMap((content: CopyableContent) => {
        if (content.type === "text" && typeof content.text === "string") {
          return [content.text];
        }

        if (content.type === "refusal" && typeof content.refusal === "string") {
          return [content.refusal];
        }

        return [];
      });
    });

    return chunks.filter(Boolean).join("\n\n").trim();
  };

  return collectText(true) || JSON.stringify(response);
}

async function copyText(text: string) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);

  let copied = false;
  try {
    textarea.focus();
    textarea.select();
    copied = document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }

  if (!copied) {
    throw new Error("Failed to copy text");
  }
}

function buildModelError(): Response {
  return new Response(
    JSON.stringify({
      error: "Model not configured",
      message: "Please configure a model first",
    }),
    { status: 400, headers: { "Content-Type": "application/json" } },
  );
}

function cloneRuntimeMessages(
  messages: RuntimeUiMessage[],
): RuntimeUiMessage[] {
  return JSON.parse(JSON.stringify(messages)) as RuntimeUiMessage[];
}

function cloneValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function isFinalResponseStatus(status?: string): boolean {
  return (
    status === AgentScopeRuntimeRunStatus.Completed ||
    status === AgentScopeRuntimeRunStatus.Failed ||
    status === AgentScopeRuntimeRunStatus.Canceled
  );
}

function hasRenderableOutput(response: StreamResponseData): boolean {
  if (response.status === AgentScopeRuntimeRunStatus.Failed) {
    return true;
  }

  return (
    response.output?.some((message) => (message.content?.length ?? 0) > 0) ??
    false
  );
}

function getResponseCardData(
  message?: RuntimeUiMessage,
): StreamResponseData | null {
  const responseCard = message?.cards?.find(
    (card) => card.code === "AgentScopeRuntimeResponseCard",
  );

  if (!responseCard?.data) {
    return null;
  }

  return cloneValue(responseCard.data as StreamResponseData);
}

function encodeSseChunk(chunk: SseChunk): Uint8Array {
  const lines: string[] = [];

  if (typeof chunk.event === "string") {
    lines.push(`event: ${chunk.event}`);
  }

  Object.entries(chunk).forEach(([key, value]) => {
    if (key === "event" || typeof value !== "string") {
      return;
    }
    lines.push(`${key}: ${value}`);
  });

  return sseEncoder.encode(`${lines.join("\n")}\n\n`);
}

function hasMessageContent(data: RuntimeStreamEvent): boolean {
  return Array.isArray(data.content) && data.content.length > 0;
}

function isEmptyAssistantPlaceholder(
  data: RuntimeStreamEvent,
): data is RuntimeStreamEvent & { id: string } {
  return (
    data.object === "message" &&
    data.role === "assistant" &&
    data.type === AgentScopeRuntimeMessageType.MESSAGE &&
    typeof data.id === "string" &&
    !hasMessageContent(data)
  );
}

function buildSyntheticAssistantMessage(
  pendingMessage: PendingAssistantMessage,
  status?: string,
): RuntimeStreamEvent {
  const nextStatus =
    status ?? pendingMessage.data.status ?? AgentScopeRuntimeRunStatus.Created;

  return {
    ...pendingMessage.data,
    status: nextStatus,
    content: [
      {
        type: "text",
        text: EMPTY_ASSISTANT_PLACEHOLDER,
        status: nextStatus,
      },
    ],
  };
}

function createRenderableUiStream(
  readableStream: ReadableStream<Uint8Array>,
  onStreamEnd?: () => void,
): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      let pendingAssistantMessage: PendingAssistantMessage | null = null;
      let hasRenderableOutput = false;

      const emitChunk = (chunk: SseChunk) => {
        controller.enqueue(encodeSseChunk(chunk));
      };

      const emitData = (data: RuntimeStreamEvent, event?: string) => {
        const chunk: SseChunk = {
          data: JSON.stringify(data),
        };

        if (event) {
          chunk.event = event;
        }

        emitChunk(chunk);
      };

      void (async () => {
        try {
          for await (const chunk of Stream({ readableStream })) {
            const sseChunk = chunk as SseChunk;

            let chunkData: RuntimeStreamEvent;
            try {
              chunkData = JSON.parse(sseChunk.data) as RuntimeStreamEvent;
            } catch {
              emitChunk(sseChunk);
              continue;
            }

            if (isEmptyAssistantPlaceholder(chunkData)) {
              pendingAssistantMessage = {
                chunk: sseChunk,
                data: chunkData,
              };
              continue;
            }

            if (
              pendingAssistantMessage &&
              chunkData.object === "content" &&
              chunkData.msg_id === pendingAssistantMessage.data.id
            ) {
              emitChunk(pendingAssistantMessage.chunk);
              pendingAssistantMessage = null;
              emitChunk(sseChunk);
              hasRenderableOutput = true;
              continue;
            }

            if (
              pendingAssistantMessage &&
              chunkData.object === "message" &&
              chunkData.id === pendingAssistantMessage.data.id
            ) {
              if (isEmptyAssistantPlaceholder(chunkData)) {
                pendingAssistantMessage = {
                  chunk: sseChunk,
                  data: chunkData,
                };
                continue;
              }

              emitChunk(sseChunk);
              pendingAssistantMessage = null;
              hasRenderableOutput =
                hasRenderableOutput || hasMessageContent(chunkData);
              continue;
            }

            if (
              chunkData.object === "response" &&
              isFinalResponseStatus(chunkData.status)
            ) {
              if (pendingAssistantMessage && !hasRenderableOutput) {
                emitData(
                  buildSyntheticAssistantMessage(
                    pendingAssistantMessage,
                    chunkData.status,
                  ),
                  pendingAssistantMessage.chunk.event,
                );
                hasRenderableOutput = true;
              }

              pendingAssistantMessage = null;
              emitChunk(sseChunk);
              continue;
            }

            hasRenderableOutput =
              hasRenderableOutput ||
              hasMessageContent(chunkData) ||
              chunkData.object === "content";
            emitChunk(sseChunk);
          }

          if (pendingAssistantMessage && !hasRenderableOutput) {
            emitData(
              buildSyntheticAssistantMessage(pendingAssistantMessage),
              pendingAssistantMessage.chunk.event,
            );
          }

          controller.close();
        } catch (error) {
          controller.error(error);
        } finally {
          onStreamEnd?.();
        }
      })();
    },
  });
}

function getStreamingAssistantMessageId(
  messages: RuntimeUiMessage[],
): string | null {
  return (
    [...messages]
      .reverse()
      .find(
        (message) =>
          message.role === "assistant" &&
          (message.msgStatus === "generating" ||
            (message.cards?.length ?? 0) === 0),
      )?.id ||
    [...messages].reverse().find((message) => message.role === "assistant")
      ?.id ||
    null
  );
}

function RuntimeLoadingBridge({
  bridgeRef,
}: {
  bridgeRef: { current: RuntimeLoadingBridgeApi | null };
}) {
  const { setLoading, getLoading } = useChatAnywhereInput(
    (value) =>
      ({
        setLoading: value.setLoading,
        getLoading: value.getLoading,
      }) as RuntimeLoadingBridgeApi,
  );

  useEffect(() => {
    if (!setLoading || !getLoading) {
      bridgeRef.current = null;
      return;
    }

    bridgeRef.current = {
      setLoading,
      getLoading,
    };

    return () => {
      if (bridgeRef.current?.setLoading === setLoading) {
        bridgeRef.current = null;
      }
    };
  }, [getLoading, setLoading, bridgeRef]);

  return null;
}

function QuickPromptBar({
  chatRef,
  agentId,
}: {
  chatRef: { current: IAgentScopeRuntimeWebUIRef | null };
  agentId?: string;
}) {
  const { t } = useTranslation();
  const { loading, disabled } = useChatAnywhereInput((value) => ({
    loading: Boolean(value.loading),
    disabled: Boolean(value.disabled),
  }));
  const [prompts, setPrompts] = useState<string[]>(() => loadQuickPrompts(agentId));
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState<string[]>(() => loadQuickPrompts(agentId));

  useEffect(() => {
    const nextPrompts = loadQuickPrompts(agentId);
    setPrompts(nextPrompts);
    setDrafts(nextPrompts);
    setEditing(false);
  }, [agentId]);

  useEffect(() => {
    persistQuickPrompts(agentId, prompts);
  }, [agentId, prompts]);

  const startEditing = () => {
    setDrafts(prompts);
    setEditing(true);
  };

  const cancelEditing = () => {
    setDrafts(prompts);
    setEditing(false);
  };

  const saveEditing = () => {
    const nextPrompts = normalizeQuickPrompts(drafts);
    setPrompts(nextPrompts);
    setEditing(false);
  };

  const updateDraft = (index: number, value: string) => {
    setDrafts((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? value : item)),
    );
  };

  const addDraft = () => {
    setDrafts((current) =>
      current.length >= MAX_QUICK_PROMPTS ? current : [...current, ""],
    );
  };

  const removeDraft = (index: number) => {
    setDrafts((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const submitPrompt = (prompt: string) => {
    const query = prompt.trim();
    if (!query || Boolean(loading) || Boolean(disabled)) {
      return;
    }
    chatRef.current?.input.submit({ query });
  };

  return (
    <>
      <ChatInput.BeforeUIContainer>
        <div className={styles.quickPromptPanel}>
          {prompts.length > 0 ? (
            <div className={styles.quickPromptList}>
              {prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className={styles.quickPromptChip}
                  onClick={() => submitPrompt(prompt)}
                  disabled={Boolean(loading) || Boolean(disabled)}
                >
                  {prompt}
                </button>
              ))}
              <button
                type="button"
                className={`${styles.quickPromptChip} ${styles.quickPromptActionChip}`}
                onClick={startEditing}
                aria-label={t("common.edit")}
              >
                <EditOutlined />
              </button>
            </div>
          ) : (
            <div className={styles.quickPromptEmptyState}>
              <span>{t("chat.quickPrompts.empty")}</span>
              <button
                type="button"
                className={`${styles.quickPromptChip} ${styles.quickPromptActionChip}`}
                onClick={startEditing}
              >
                {t("chat.quickPrompts.add")}
              </button>
            </div>
          )}
        </div>
      </ChatInput.BeforeUIContainer>

      <SparkModal
        open={editing}
        title={t("chat.quickPrompts.label")}
        width={520}
        destroyOnHidden
        onCancel={cancelEditing}
        onOk={saveEditing}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        okButtonProps={{
          icon: <SaveOutlined />,
          className: styles.quickPromptSaveButton,
        }}
        cancelButtonProps={{ icon: <CloseOutlined /> }}
      >
        <div className={`${styles.quickPromptEditor} ${styles.quickPromptModalBody}`}>
          <div className={styles.quickPromptModalToolbar}>
            <div className={styles.quickPromptModalMeta}>
              <span className={styles.quickPromptModalCounter}>
                {drafts.length}/{MAX_QUICK_PROMPTS}
              </span>
            </div>
            <Button
              size="small"
              onClick={addDraft}
              disabled={drafts.length >= MAX_QUICK_PROMPTS}
              icon={<PlusOutlined />}
              className={styles.quickPromptAddButton}
            >
              {t("chat.quickPrompts.add")}
            </Button>
          </div>
          <div className={styles.quickPromptEditorList}>
            {drafts.map((prompt, index) => (
              <div key={index} className={styles.quickPromptEditorRow}>
                <span className={styles.quickPromptRowIndex}>{index + 1}</span>
                <Input
                  value={prompt}
                  maxLength={60}
                  placeholder={t("chat.quickPrompts.placeholder")}
                  className={styles.quickPromptInput}
                  onChange={(event) => updateDraft(index, event.target.value)}
                />
                <Button
                  danger
                  size="small"
                  type="text"
                  icon={<DeleteOutlined />}
                  onClick={() => removeDraft(index)}
                  aria-label={t("common.delete")}
                  className={styles.quickPromptDeleteButton}
                />
              </div>
            ))}
            {drafts.length === 0 && (
              <div className={styles.quickPromptEmpty}>
                {t("chat.quickPrompts.empty")}
              </div>
            )}
          </div>
        </div>
      </SparkModal>
    </>
  );
}

function ChatHeaderControls({
  bridgeRef,
}: {
  bridgeRef: { current: RuntimeLoadingBridgeApi | null };
}) {
  const { chatThemeKey, setChatThemeKey, isDark } = useChatThemeContext();

  return (
    <div className={styles.headerControls}>
      <RuntimeLoadingBridge bridgeRef={bridgeRef} />
      <ModelSelector />
      <ChatThemeSelector
        value={chatThemeKey}
        isDark={isDark}
        onChange={setChatThemeKey}
      />
    </div>
  );
}

const RuntimeChat = memo(function RuntimeChat({
  chatRef,
  refreshKey,
  options,
}: {
  chatRef: { current: IAgentScopeRuntimeWebUIRef | null };
  refreshKey: number;
  options: IAgentScopeRuntimeWebUIOptions;
}) {
  return (
    <AgentScopeRuntimeWebUI
      ref={chatRef}
      key={refreshKey}
      options={options}
    />
  );
});

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { isDark } = useTheme();
  const chatId = useMemo(() => {
    const match = location.pathname.match(/^\/chat\/(.+)$/);
    return match?.[1];
  }, [location.pathname]);
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const { selectedAgent } = useAgentStore();
  const [refreshKey, setRefreshKey] = useState(0);
  const [chatThemeKey, setChatThemeKey] =
    useState<ChatThemeKey>(getStoredChatTheme);
  const [chatStatus, setChatStatus] = useState<"idle" | "running">("idle");
  const [, setReconnectStreaming] = useState(false);
  const reconnectTriggeredForRef = useRef<string | null>(null);
  const prevChatIdRef = useRef<string | undefined>(undefined);
  const runtimeLoadingBridgeRef = useRef<RuntimeLoadingBridgeApi | null>(null);
  const chatTheme = useMemo(
    () => getChatTheme(chatThemeKey, isDark),
    [chatThemeKey, isDark],
  );
  const handleChatThemeChange = useCallback((theme: ChatThemeKey) => {
    startTransition(() => {
      setChatThemeKey(theme);
    });
  }, []);
  const chatThemeStyle = useMemo(
    () =>
      ({
        "--theme-picker-accent": chatTheme.palette.themePickerAccent,
        "--chat-color-bg-base": chatTheme.palette.colorBgBase,
        "--chat-color-text-base": chatTheme.palette.colorTextBase,
        "--chat-shell-background": chatTheme.palette.shellBackground,
        "--chat-layout-background": chatTheme.palette.background,
        "--chat-panel-background": chatTheme.palette.panelBackground,
        "--chat-header-background": chatTheme.palette.headerBackground,
        "--chat-header-border": chatTheme.palette.headerBorder,
        "--chat-border-color": chatTheme.palette.borderColor,
        "--chat-border-soft-color": chatTheme.palette.borderSoftColor,
        "--chat-shadow-color": chatTheme.palette.shadowColor,
        "--chat-assistant-bubble": chatTheme.palette.assistantBubble,
        "--chat-sender-background": chatTheme.palette.senderBackground,
        "--chat-prompt-background": chatTheme.palette.promptBackground,
        "--chat-prompt-hover-background":
          chatTheme.palette.promptHoverBackground,
        "--chat-conversation-hover": chatTheme.palette.conversationHover,
        "--chat-conversation-active": chatTheme.palette.conversationActive,
        "--chat-scroll-thumb": chatTheme.palette.scrollThumb,
        "--chat-primary-color": chatTheme.palette.colorPrimary,
        "--assistant-text": chatTheme.palette.assistantText,
        "--assistant-heading": chatTheme.palette.assistantHeading,
        "--assistant-link": chatTheme.palette.assistantLink,
        "--assistant-surface": chatTheme.palette.assistantSurface,
        "--assistant-border": chatTheme.palette.assistantBorder,
        "--assistant-shadow": chatTheme.palette.assistantShadow,
        "--assistant-radius": chatTheme.palette.assistantRadius,
        "--assistant-padding": chatTheme.palette.assistantPadding,
        "--assistant-backdrop-filter": chatTheme.palette.assistantBackdropFilter,
        "--assistant-font-family": chatTheme.palette.assistantFontFamily,
        "--assistant-h1-border": chatTheme.palette.assistantH1Border,
        "--assistant-h2-bg": chatTheme.palette.assistantH2Bg,
        "--assistant-h2-text": chatTheme.palette.assistantH2Text,
        "--assistant-h2-border": chatTheme.palette.assistantH2Border,
        "--assistant-h2-shadow": chatTheme.palette.assistantH2Shadow,
        "--assistant-h3-accent": chatTheme.palette.assistantH3Accent,
        "--assistant-h3-glow": chatTheme.palette.assistantH3Glow,
        "--assistant-h4-text": chatTheme.palette.assistantH4Text,
        "--assistant-strong-bg": chatTheme.palette.assistantStrongBg,
        "--assistant-strong-text": chatTheme.palette.assistantStrongText,
        "--assistant-emphasis": chatTheme.palette.assistantEmphasis,
        "--assistant-marker": chatTheme.palette.assistantMarker,
        "--assistant-mark-bg": chatTheme.palette.assistantMarkBg,
        "--assistant-mark-text": chatTheme.palette.assistantMarkText,
        "--assistant-blockquote-bg": chatTheme.palette.assistantBlockquoteBg,
        "--assistant-quote-border": chatTheme.palette.assistantQuoteBorder,
        "--assistant-inline-code-bg": chatTheme.palette.assistantInlineCodeBg,
        "--assistant-inline-code-border":
          chatTheme.palette.assistantInlineCodeBorder,
        "--assistant-code-bg": chatTheme.palette.assistantCodeBg,
        "--assistant-code-header": chatTheme.palette.assistantCodeHeader,
        "--assistant-code-text": chatTheme.palette.assistantCodeText,
        "--assistant-table-bg": chatTheme.palette.assistantTableBg,
        "--assistant-table-head-bg": chatTheme.palette.assistantTableHeadBg,
        "--assistant-table-head-text":
          chatTheme.palette.assistantTableHeadText,
        "--assistant-table-border": chatTheme.palette.assistantTableBorder,
        "--assistant-hr": chatTheme.palette.assistantHr,
        "--assistant-image-shadow": chatTheme.palette.assistantImageShadow,
      }) as CSSProperties,
    [chatTheme],
  );
  const chatThemeContextValue = useMemo(
    () => ({
      chatThemeKey,
      setChatThemeKey: handleChatThemeChange,
      isDark,
    }),
    [chatThemeKey, handleChatThemeChange, isDark],
  );

  const isComposingRef = useRef(false);
  const isChatActiveRef = useRef(false);
  isChatActiveRef.current =
    location.pathname === "/" || location.pathname.startsWith("/chat");

  const lastSessionIdRef = useRef<string | null>(null);
  const chatIdRef = useRef(chatId);
  const navigateRef = useRef(navigate);
  const chatRef = useRef<IAgentScopeRuntimeWebUIRef>(null);
  chatIdRef.current = chatId;
  navigateRef.current = navigate;

  useEffect(() => {
    sessionApi.setChatRef(chatRef);
    return () => sessionApi.setChatRef(null);
  }, []);

  useEffect(() => {
    persistChatTheme(chatThemeKey);
  }, [chatThemeKey]);

  useEffect(() => {
    const handleCompositionStart = () => {
      if (!isChatActiveRef.current) return;
      isComposingRef.current = true;
    };

    const handleCompositionEnd = () => {
      if (!isChatActiveRef.current) return;
      setTimeout(() => {
        isComposingRef.current = false;
      }, 150);
    };

    const handleKeyPress = (e: KeyboardEvent) => {
      if (!isChatActiveRef.current) return;
      const target = e.target as HTMLElement;
      if (target?.tagName === "TEXTAREA" && e.key === "Enter" && !e.shiftKey) {
        if (isComposingRef.current || e.isComposing) {
          e.stopPropagation();
          e.stopImmediatePropagation();
          return false;
        }
      }
    };

    document.addEventListener("compositionstart", handleCompositionStart, true);
    document.addEventListener("compositionend", handleCompositionEnd, true);
    document.addEventListener("keypress", handleKeyPress, true);

    return () => {
      document.removeEventListener(
        "compositionstart",
        handleCompositionStart,
        true,
      );
      document.removeEventListener(
        "compositionend",
        handleCompositionEnd,
        true,
      );
      document.removeEventListener("keypress", handleKeyPress, true);
    };
  }, []);

  useEffect(() => {
    sessionApi.onSessionIdResolved = (tempId, realId) => {
      if (!isChatActiveRef.current) return;
      if (chatIdRef.current === tempId) {
        lastSessionIdRef.current = realId;
        navigateRef.current(`/chat/${realId}`, { replace: true });
      }
    };

    sessionApi.onSessionRemoved = (removedId) => {
      if (!isChatActiveRef.current) return;
      if (chatIdRef.current === removedId) {
        lastSessionIdRef.current = null;
        navigateRef.current("/chat", { replace: true });
      }
    };

    return () => {
      sessionApi.onSessionIdResolved = null;
      sessionApi.onSessionRemoved = null;
    };
  }, []);

  // Fetch chat status when viewing a chat (for running indicator and reconnect)
  useEffect(() => {
    if (!chatId || chatId === "undefined" || chatId === "null") {
      setChatStatus("idle");
      return;
    }
    const realId = sessionApi.getRealIdForSession(chatId) ?? chatId;
    api.getChat(realId).then(
      (res) => setChatStatus((res.status as "idle" | "running") ?? "idle"),
      () => setChatStatus("idle"),
    );
  }, [chatId]);

  // Trigger reconnect when session status becomes "running" so the library
  // consumes the SSE stream. Done here (not in sessionApi.getSession) so we
  // run after React has updated and the chat input ref is ready, avoiding
  // a fixed timeout and race conditions.
  useEffect(() => {
    if (prevChatIdRef.current !== chatId) {
      prevChatIdRef.current = chatId;
      reconnectTriggeredForRef.current = null;
    }
    if (!chatId || chatStatus !== "running") return;
    if (reconnectTriggeredForRef.current === chatId) return;
    reconnectTriggeredForRef.current = chatId;
    sessionApi.triggerReconnectSubmit();
  }, [chatId, chatStatus]);

  // Refresh chat when selectedAgent changes
  const prevSelectedAgentRef = useRef(selectedAgent);
  useEffect(() => {
    // Only refresh if selectedAgent actually changed (not initial mount)
    if (
      prevSelectedAgentRef.current !== selectedAgent &&
      prevSelectedAgentRef.current !== undefined
    ) {
      // Force re-render by updating refresh key
      setRefreshKey((prev) => prev + 1);
    }
    prevSelectedAgentRef.current = selectedAgent;
  }, [selectedAgent]);

  const getSessionListWrapped = useCallback(async () => {
    const sessions = await sessionApi.getSessionList();
    const currentChatId = chatIdRef.current;

    if (currentChatId) {
      const idx = sessions.findIndex((s) => s.id === currentChatId);
      if (idx > 0) {
        return [
          sessions[idx],
          ...sessions.slice(0, idx),
          ...sessions.slice(idx + 1),
        ];
      }
    }

    return sessions;
  }, []);

  const getSessionWrapped = useCallback(async (sessionId: string) => {
    const currentChatId = chatIdRef.current;

    if (
      isChatActiveRef.current &&
      sessionId &&
      sessionId !== lastSessionIdRef.current &&
      sessionId !== currentChatId
    ) {
      const urlId = sessionApi.getRealIdForSession(sessionId) ?? sessionId;
      lastSessionIdRef.current = urlId;
      navigateRef.current(`/chat/${urlId}`, { replace: true });
    }

    return sessionApi.getSession(sessionId);
  }, []);

  const createSessionWrapped = useCallback(async (session: Partial<IAgentScopeRuntimeWebUISession>) => {
    const result = await sessionApi.createSession(session);
    const newSessionId = session?.id || result[0]?.id;
    if (isChatActiveRef.current && newSessionId) {
      lastSessionIdRef.current = newSessionId;
      navigateRef.current(`/chat/${newSessionId}`, { replace: true });
    }
    return result;
  }, []);

  const wrappedSessionApi = useMemo(
    () => ({
      getSessionList: getSessionListWrapped,
      getSession: getSessionWrapped,
      createSession: createSessionWrapped,
      updateSession: sessionApi.updateSession.bind(sessionApi),
      removeSession: sessionApi.removeSession.bind(sessionApi),
    }),
    [createSessionWrapped, getSessionListWrapped, getSessionWrapped],
  );

  const copyResponse = useCallback(
    async (response: CopyableResponse) => {
      try {
        await copyText(extractCopyableText(response));
        message.success(t("common.copied"));
      } catch {
        message.error(t("common.copyFailed"));
      }
    },
    [t],
  );

  const persistSessionMessages = useCallback(
    async (sessionId: string, messages: RuntimeUiMessage[]) => {
      if (!sessionId) return;
      await sessionApi.updateSession({
        id: sessionId,
        messages: cloneRuntimeMessages(messages),
      });
    },
    [],
  );

  const releaseStaleLoadingState = useCallback((sessionId: string) => {
    const activeChatId = chatIdRef.current;
    const realSessionId = sessionApi.getRealIdForSession(sessionId);
    const isBackgroundSession =
      activeChatId !== sessionId && activeChatId !== realSessionId;

    if (!isBackgroundSession) {
      return;
    }

    if (sessionApi.hasLiveMessagesForSession(activeChatId)) {
      return;
    }

    runtimeLoadingBridgeRef.current?.setLoading?.(false);
  }, []);

  const persistStreamSession = useCallback(
    (sessionId: string, readableStream: ReadableStream<Uint8Array>) => {
      const initialMessages = cloneRuntimeMessages(
        (chatRef.current?.messages.getMessages() as RuntimeUiMessage[]) || [],
      );
      const assistantMessageId =
        getStreamingAssistantMessageId(initialMessages) ||
        `stream-${sessionId}`;
      const responseBuilder = new AgentScopeRuntimeResponseBuilder({
        id: "",
        status: AgentScopeRuntimeRunStatus.Created,
        created_at: 0,
      });

      void (async () => {
        let cachedMessages = initialMessages;
        let hasStreamActivity = false;
        let didReleaseLoading = false;

        try {
          for await (const chunk of Stream({ readableStream })) {
            let chunkData: unknown;
            try {
              chunkData = JSON.parse(chunk.data);
            } catch {
              continue;
            }

            hasStreamActivity = true;
            const responseData = responseBuilder.handle(
              chunkData as never,
            ) as StreamResponseData;
            const isFinalChunk = isFinalResponseStatus(responseData.status);
            const existingAssistantMessage = cachedMessages.find(
              (message) => message.id === assistantMessageId,
            );
            const previousResponseData = getResponseCardData(
              existingAssistantMessage,
            );

            let nextResponseData: StreamResponseData | null = null;
            if (hasRenderableOutput(responseData)) {
              nextResponseData = cloneValue(responseData);
            } else if (isFinalChunk && previousResponseData) {
              nextResponseData = {
                ...previousResponseData,
                status: responseData.status ?? previousResponseData.status,
              };
            }

            if (nextResponseData) {
              const assistantMessage: RuntimeUiMessage = {
                ...(existingAssistantMessage || {
                  id: assistantMessageId,
                  role: "assistant",
                }),
                id: assistantMessageId,
                role: "assistant",
                cards: [
                  {
                    code: "AgentScopeRuntimeResponseCard",
                    data: nextResponseData,
                  },
                ],
                msgStatus: isFinalChunk ? "finished" : "generating",
              };

              const assistantIndex = cachedMessages.findIndex(
                (message) => message.id === assistantMessageId,
              );
              cachedMessages =
                assistantIndex >= 0
                  ? [
                      ...cachedMessages.slice(0, assistantIndex),
                      assistantMessage,
                      ...cachedMessages.slice(assistantIndex + 1),
                    ]
                  : [...cachedMessages, assistantMessage];

              await persistSessionMessages(sessionId, cachedMessages);
            }

            if (!isFinalChunk) {
              continue;
            }

            releaseStaleLoadingState(sessionId);
            didReleaseLoading = true;
          }
        } catch (error) {
          console.error("Failed to persist background chat stream:", error);
        } finally {
          if (hasStreamActivity && !didReleaseLoading) {
            releaseStaleLoadingState(sessionId);
          }
        }
      })();
    },
    [persistSessionMessages, releaseStaleLoadingState],
  );

  const customFetch = useCallback(
    async (data: ChatFetchPayload): Promise<Response> => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      const token = getApiToken();
      if (token) headers.Authorization = `Bearer ${token}`;
      try {
        const agentStorage = localStorage.getItem("copaw-agent-storage");
        if (agentStorage) {
          const parsed = JSON.parse(agentStorage);
          const selectedAgent = parsed?.state?.selectedAgent;
          if (selectedAgent) {
            headers["X-Agent-Id"] = selectedAgent;
          }
        }
      } catch (error) {
        console.warn("Failed to get selected agent from storage:", error);
      }

      const shouldReconnect =
        data.reconnect || data.biz_params?.reconnect === true;
      const reconnectSessionId =
        data.session_id ?? window.currentSessionId ?? "";
      if (shouldReconnect && reconnectSessionId) {
        const res = await fetch(getApiUrl("/console/chat"), {
          method: "POST",
          headers,
          body: JSON.stringify({
            reconnect: true,
            session_id: reconnectSessionId,
            user_id: data.user_id ?? window.currentUserId ?? "default",
            channel: data.channel ?? window.currentChannel ?? "console",
          }),
        });
        if (!res.ok || !res.body) return res;
        const onStreamEnd = () => {
          setChatStatus("idle");
          setReconnectStreaming(false);
        };
        const transformed = createRenderableUiStream(res.body, onStreamEnd);
        return new Response(transformed, {
          headers: res.headers,
          status: res.status,
        });
      }

      try {
        const activeModels = await providerApi.getActiveModels();
        if (
          !activeModels?.active_llm?.provider_id ||
          !activeModels?.active_llm?.model
        ) {
          setShowModelPrompt(true);
          return buildModelError();
        }
      } catch {
        setShowModelPrompt(true);
        return buildModelError();
      }

      const { input = [], biz_params } = data;
      const session = input[input.length - 1]?.session || {};
      const lastInput = input.slice(-1);
      const lastMsg = lastInput[0];
      const rewrittenInput =
        lastMsg?.content && Array.isArray(lastMsg.content)
          ? [
              {
                ...lastMsg,
                content: lastMsg.content.map((part: ChatInputPart) => {
                  const p: ChatInputPart = { ...part };
                  const toStoredName = (v: string) => {
                    const m1 = v.match(/\/console\/files\/[^/]+\/(.+)$/);
                    if (m1) return m1[1];
                    const m2 = v.match(/^[^/]+\/(.+)$/);
                    if (m2) return m2[1];
                    return v;
                  };
                  if (p.type === "image" && typeof p.image_url === "string")
                    p.image_url = toStoredName(p.image_url);
                  if (p.type === "file" && typeof p.file_url === "string")
                    p.file_url = toStoredName(p.file_url);
                  if (p.type === "audio" && typeof p.audio_url === "string")
                    p["data"] = toStoredName(p.audio_url);
                  if (p.type === "video" && typeof p.video_url === "string")
                    p.video_url = toStoredName(p.video_url);

                  return p;
                }),
              },
            ]
          : lastInput;

      const requestBody = {
        input: rewrittenInput,
        session_id: window.currentSessionId || session?.session_id || "",
        user_id: window.currentUserId || session?.user_id || "default",
        channel: window.currentChannel || session?.channel || "console",
        stream: true,
        ...biz_params,
      };

      const response = await fetch(getApiUrl("/console/chat"), {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
        signal: data.signal,
      });

      if (!response.ok || !response.body || !requestBody.session_id) {
        return response;
      }

      const [uiStream, cacheStream] = response.body.tee();
      persistStreamSession(requestBody.session_id, cacheStream);

      return new Response(createRenderableUiStream(uiStream), {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      });
    },
    [persistStreamSession, setChatStatus, setReconnectStreaming],
  );

  const options = useMemo(() => {
    const i18nConfig = getDefaultConfig(t);

    const handleBeforeSubmit = async () => {
      if (isComposingRef.current) return false;
      return true;
    };

    return {
      ...i18nConfig,
      theme: {
        ...defaultConfig.theme,
        colorPrimary: RUNTIME_CHAT_THEME.colorPrimary,
        colorBgBase: RUNTIME_CHAT_THEME.colorBgBase,
        colorTextBase: RUNTIME_CHAT_THEME.colorTextBase,
        darkMode: RUNTIME_CHAT_THEME.darkMode,
        background: RUNTIME_CHAT_THEME.background,
        leftHeader: {
          ...defaultConfig.theme.leftHeader,
        },
        rightHeader: <ChatHeaderControls bridgeRef={runtimeLoadingBridgeRef} />,
      },
      welcome: {
        ...i18nConfig.welcome,
        avatar: `${import.meta.env.BASE_URL}babyclaw.png`,
      },
      sender: {
        ...((i18nConfig as { sender?: Record<string, unknown> }).sender ?? {}),
        disclaimer: "",
        beforeSubmit: handleBeforeSubmit,
        beforeUI: <QuickPromptBar chatRef={chatRef} agentId={selectedAgent} />,
        rootClassName: styles.runtimeSenderRoot,
        classNames: {
          input: styles.runtimeSenderInput,
        },
        styles: {
          input: {
            background: "transparent",
            border: "none",
            boxShadow: "none",
            outline: "none",
          },
        },
        attachments: {
          trigger: function (props: { disabled?: boolean }) {
            return (
              <IconButton
                disabled={props?.disabled}
                icon={<SparkAttachmentLine />}
                bordered={false}
                aria-label={t("chat.attachments.tooltip")}
              />
            );
          },
          accept: "*/*",
          customRequest: async (options: {
            file: File;
            onSuccess: (body: { url?: string; thumbUrl?: string }) => void;
            onError?: (e: Error) => void;
            onProgress?: (e: { percent?: number }) => void;
          }) => {
            try {
              console.log("options.file", options.file);

              // Check file size limit (10MB)
              const file = options.file as File;
              const isLt10M = file.size / 1024 / 1024 < 10;
              if (!isLt10M) {
                message.error(t("chat.attachments.fileSizeLimit"));
                return options.onError?.(new Error("File size exceeds 10MB"));
              }

              options.onProgress?.({ percent: 0 });
              const res = await chatApi.uploadFile(options.file);
              options.onProgress?.({ percent: 100 });
              options.onSuccess({ url: chatApi.fileUrl(res.url) });
            } catch (e) {
              options.onError?.(e instanceof Error ? e : new Error(String(e)));
            }
          },
        },
      },
      session: { multiple: true, api: wrappedSessionApi },
      api: {
        ...defaultConfig.api,
        fetch: customFetch,
        cancel(data: { session_id: string }) {
          const chatIdForStop = data?.session_id
            ? (sessionApi.getRealIdForSession(data.session_id) ??
              data.session_id)
            : "";
          if (chatIdForStop) {
            chatApi.stopConsoleChat(chatIdForStop).then(
              () => setChatStatus("idle"),
              (err) => {
                console.error("stopConsoleChat failed:", err);
              },
            );
          }
        },
      },
      actions: {
        list: [
          {
            icon: <SparkCopyLine />,
            onClick: ({ data }: { data: CopyableResponse }) => {
              void copyResponse(data);
            },
          },
        ],
        replace: true,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [
    wrappedSessionApi,
    customFetch,
    copyResponse,
    selectedAgent,
    t,
  ]);

  return (
    <ChatThemeContext.Provider value={chatThemeContextValue}>
      <div
        className={styles.chatPage}
        style={chatThemeStyle}
        data-content-theme={chatThemeKey}
      >
        <div className={styles.chatViewport}>
          <RuntimeChat
            chatRef={chatRef}
            refreshKey={refreshKey}
            options={options}
          />
        </div>

        <Modal
          open={showModelPrompt}
          closable={false}
          footer={null}
          width={480}
        >
          <Result
            icon={<ExclamationCircleOutlined style={{ color: "#faad14" }} />}
            title={t("modelConfig.promptTitle")}
            subTitle={t("modelConfig.promptMessage")}
            extra={[
              <Button key="skip" onClick={() => setShowModelPrompt(false)}>
                {t("modelConfig.skipButton")}
              </Button>,
              <Button
                key="configure"
                type="primary"
                icon={<SettingOutlined />}
                onClick={() => {
                  setShowModelPrompt(false);
                  navigate("/models");
                }}
              >
                {t("modelConfig.configureButton")}
              </Button>,
            ]}
          />
        </Modal>
      </div>
    </ChatThemeContext.Provider>
  );
}
