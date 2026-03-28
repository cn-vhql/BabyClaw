import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Card,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Spinner,
  Switch,
  Tabs,
  Tag,
  message,
} from "@agentscope-ai/design";
import { Pagination, TimePicker } from "antd";
import dayjs from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import { useTranslation } from "react-i18next";

import api from "../../api";
import type { ChannelConfig } from "../../api/types";
import type {
  FocusNoteDetail,
  FocusNoteSummary,
  FocusRunArchive,
  FocusRunDetail,
  FocusRunRecord,
  FocusRunStatus,
  FocusSettings,
} from "../../api/types/focus";
import { LazyMarkdown } from "../../components/LazyMarkdown";
import {
  parseEvery,
  serializeEvery,
  type EveryUnit,
} from "../Control/Heartbeat/parseEvery";
import { useAgentStore } from "../../stores/agentStore";
import styles from "./index.module.less";

dayjs.extend(customParseFormat);

const TIME_FORMAT = "HH:mm";
const NOTE_PAGE_SIZE = 10;
const RUN_PAGE_SIZE = 8;

const EVERY_UNIT_OPTIONS: { value: EveryUnit; labelKey: string }[] = [
  { value: "m", labelKey: "focus.unitMinutes" },
  { value: "h", labelKey: "focus.unitHours" },
];

type FocusFormValues = Omit<FocusSettings, "every" | "doNotDisturb"> & {
  everyNumber?: number;
  everyUnit?: EveryUnit;
  useDoNotDisturb?: boolean;
  doNotDisturbStart?: string;
  doNotDisturbEnd?: string;
};

type RunFilterValue = "all" | FocusRunStatus;
type RunTabKey = "overview" | "notes" | "prompt" | "output" | "tools" | "notification";
type NormalizedToolLog = {
  key: string;
  tool: string;
  callId?: string;
  timestamp?: string;
  args?: unknown;
  result?: unknown;
};

function TimePickerHHmm({
  value,
  onChange,
}: {
  value?: string | null;
  onChange?: (s: string) => void;
}) {
  return (
    <TimePicker
      format={TIME_FORMAT}
      value={value ? dayjs(value, TIME_FORMAT) : null}
      onChange={(_, str) => {
        const nextValue = typeof str === "string" ? str : str?.[0];
        if (nextValue) onChange?.(nextValue);
      }}
      minuteStep={15}
      needConfirm={false}
      style={{ width: "100%" }}
    />
  );
}

function formatTimestamp(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return dayjs(date).format("YYYY-MM-DD HH:mm");
}

function extractRequestError(error: unknown, fallback: string): string {
  if (!(error instanceof Error) || !error.message) {
    return fallback;
  }

  const separatorIndex = error.message.indexOf(" - ");
  if (separatorIndex === -1) {
    return error.message || fallback;
  }

  const responseText = error.message.slice(separatorIndex + 3).trim();
  try {
    const parsed = JSON.parse(responseText) as {
      detail?: string | Array<{ loc?: Array<string | number>; msg?: string }>;
    };

    if (typeof parsed.detail === "string" && parsed.detail) {
      return parsed.detail;
    }

    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      return parsed.detail
        .map((item) => {
          const location = item.loc?.join(".") || "body";
          return item.msg ? `${location}: ${item.msg}` : location;
        })
        .join("; ");
    }
  } catch {
    return responseText || fallback;
  }

  return responseText || fallback;
}

function isNotFoundError(error: unknown) {
  return error instanceof Error && error.message.includes("404");
}

function renderJson(value: unknown) {
  if (value == null) return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function formatDisplayTime(timestamp?: string) {
  if (!timestamp) return "";
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return parsed.toLocaleString();
}

function stringifyValue(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function normalizeToolLogs(archive: FocusRunArchive | null): NormalizedToolLog[] {
  if (!archive || !Array.isArray(archive.toolExecutionLog)) return [];

  return archive.toolExecutionLog.map((entry, index) => {
    if (entry && typeof entry === "object") {
      const callId =
        typeof entry.call_id === "string"
          ? entry.call_id
          : typeof entry.callId === "string"
            ? entry.callId
            : undefined;
      const tool =
        typeof entry.tool === "string"
          ? entry.tool
          : typeof entry.name === "string"
            ? entry.name
            : `tool-${index + 1}`;

      return {
        key: `${callId || tool}-${index}`,
        tool,
        callId,
        timestamp: typeof entry.timestamp === "string" ? entry.timestamp : undefined,
        args:
          "args" in entry
            ? entry.args
            : "input" in entry
              ? entry.input
              : "arguments" in entry
                ? entry.arguments
                : undefined,
        result:
          "result" in entry
            ? entry.result
            : "output" in entry
              ? entry.output
              : undefined,
      };
    }

    return {
      key: `tool-${index}`,
      tool: `tool-${index + 1}`,
      result: entry,
    };
  });
}

export default function FocusPage() {
  const { t } = useTranslation();
  const { selectedAgent } = useAgentStore();
  const [form] = Form.useForm<FocusFormValues>();

  const [settings, setSettings] = useState<FocusSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [notesLoading, setNotesLoading] = useState(true);
  const [runsLoading, setRunsLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [startingRun, setStartingRun] = useState(false);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [runsDrawerOpen, setRunsDrawerOpen] = useState(false);
  const [notificationOptions, setNotificationOptions] = useState<
    { label: string; value: string }[]
  >([]);

  const [searchKeyword, setSearchKeyword] = useState("");
  const deferredSearchKeyword = useDeferredValue(searchKeyword);
  const [notePage, setNotePage] = useState(1);
  const [noteTotal, setNoteTotal] = useState(0);
  const [notes, setNotes] = useState<FocusNoteSummary[]>([]);

  const [runPage, setRunPage] = useState(1);
  const [runFilter, setRunFilter] = useState<RunFilterValue>("all");
  const [runTotal, setRunTotal] = useState(0);
  const [runs, setRuns] = useState<FocusRunRecord[]>([]);

  const [noteDetailOpen, setNoteDetailOpen] = useState(false);
  const [noteDetailLoading, setNoteDetailLoading] = useState(false);
  const [detailNote, setDetailNote] = useState<FocusNoteDetail | null>(null);

  const [runDetailOpen, setRunDetailOpen] = useState(false);
  const [runDetailLoading, setRunDetailLoading] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<FocusRunDetail | null>(null);
  const [runArchive, setRunArchive] = useState<FocusRunArchive | null>(null);
  const [activeRunTab, setActiveRunTab] = useState<RunTabKey>("overview");

  const [pageVisible, setPageVisible] = useState(
    typeof document === "undefined" ? true : !document.hidden,
  );
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const hasRunningRun = runs.some((run) => run.status === "running");
  const tags = settings?.tags || [];

  const loadSettings = async () => {
    setSettingsLoading(true);
    try {
      const [focusSettings, channelConfigs] = await Promise.all([
        api.getFocusSettings(),
        api.listChannels().catch(() => null),
      ]);

      setSettings(focusSettings);

      const everyParts = parseEvery(focusSettings.every || "6h");
      form.setFieldsValue({
        enabled: focusSettings.enabled,
        everyNumber: everyParts.number,
        everyUnit: everyParts.unit,
        notificationChannel: focusSettings.notificationChannel || "last",
        tags: focusSettings.tags || [],
        useDoNotDisturb: !!focusSettings.doNotDisturb,
        doNotDisturbStart: focusSettings.doNotDisturb?.start || "23:00",
        doNotDisturbEnd: focusSettings.doNotDisturb?.end || "08:00",
      });

      const baseOptions = [
        { label: t("focus.notificationNone"), value: "none" },
        { label: t("focus.notificationLast"), value: "last" },
      ];
      const channelEntries = Object.entries(
        (channelConfigs ?? {}) as Partial<ChannelConfig>,
      )
        .filter(([, config]) => Boolean(config?.enabled))
        .map(([key]) => ({ label: key, value: key }));
      setNotificationOptions([...baseOptions, ...channelEntries]);
    } catch (error) {
      console.error("Failed to load focus settings:", error);
      message.error(t("focus.loadFailed"));
    } finally {
      setSettingsLoading(false);
    }
  };

  const loadNotes = async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) setNotesLoading(true);
    try {
      const result = await api.listFocusNotes({
        page: notePage,
        pageSize: NOTE_PAGE_SIZE,
        q: deferredSearchKeyword.trim() || undefined,
      });
      setNotes(result.items || []);
      setNoteTotal(result.total || 0);
    } catch (error) {
      console.error("Failed to load focus notes:", error);
      if (!silent) {
        message.error(t("focus.notesLoadFailed"));
      }
    } finally {
      if (!silent) setNotesLoading(false);
    }
  };

  const loadRuns = async ({ silent = false }: { silent?: boolean } = {}) => {
    if (!silent) setRunsLoading(true);
    try {
      const result = await api.listFocusRuns({
        page: runPage,
        pageSize: RUN_PAGE_SIZE,
        status: runFilter === "all" ? undefined : runFilter,
      });
      setRuns(result.items || []);
      setRunTotal(result.total || 0);
    } catch (error) {
      console.error("Failed to load focus runs:", error);
      if (!silent) {
        message.error(t("focus.runsLoadFailed"));
      }
    } finally {
      if (!silent) setRunsLoading(false);
    }
  };

  const loadRunDetail = async (
    runId: string,
    { silent = false }: { silent?: boolean } = {},
  ) => {
    if (!silent) setRunDetailLoading(true);
    try {
      const detail = await api.getFocusRun(runId);
      setRunDetail(detail);
      try {
        const archive = await api.getFocusRunArchive(runId);
        setRunArchive(archive);
      } catch (error) {
        if (!isNotFoundError(error)) {
          throw error;
        }
        setRunArchive(null);
      }
    } catch (error) {
      console.error("Failed to load focus run detail:", error);
      if (!silent) {
        message.error(t("focus.runDetailLoadFailed"));
      }
    } finally {
      if (!silent) setRunDetailLoading(false);
    }
  };

  const refreshAll = async () => {
    await Promise.all([loadSettings(), loadNotes(), loadRuns()]);
  };

  useEffect(() => {
    setSearchKeyword("");
    setNotePage(1);
    setRunPage(1);
    setRunFilter("all");
    setDetailNote(null);
    setRunDetail(null);
    setRunArchive(null);
    setNoteDetailOpen(false);
    setRunDetailOpen(false);
    void loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent]);

  useEffect(() => {
    void loadNotes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent, notePage, deferredSearchKeyword]);

  useEffect(() => {
    void loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent, runPage, runFilter]);

  useEffect(() => {
    if (notePage !== 1) {
      setNotePage(1);
    }
  }, [deferredSearchKeyword]);

  useEffect(() => {
    if (runPage !== 1) {
      setRunPage(1);
    }
  }, [runFilter]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      setPageVisible(!document.hidden);
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  useEffect(() => {
    if (!(pageVisible && hasRunningRun)) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      return;
    }

    if (!pollingRef.current) {
      pollingRef.current = setInterval(() => {
        void loadNotes({ silent: true });
        void loadRuns({ silent: true });
        if (selectedRunId) {
          void loadRunDetail(selectedRunId, { silent: true });
        }
      }, 5000);
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [hasRunningRun, pageVisible, selectedRunId]);

  const handleSave = async (values: FocusFormValues) => {
    const payload: FocusSettings = {
      enabled: values.enabled ?? false,
      every:
        values.everyNumber != null && values.everyUnit
          ? serializeEvery({ number: values.everyNumber, unit: values.everyUnit })
          : "6h",
      notificationChannel: values.notificationChannel || "last",
      doNotDisturb:
        values.useDoNotDisturb &&
        values.doNotDisturbStart &&
        values.doNotDisturbEnd
          ? {
              start: values.doNotDisturbStart,
              end: values.doNotDisturbEnd,
            }
          : null,
      tags: (values.tags || []).map((tag) => tag.trim()).filter(Boolean),
    };

    setSaving(true);
    try {
      const saved = await api.updateFocusSettings(payload);
      setSettings(saved);
      message.success(t("focus.saveSuccess"));
      setDrawerOpen(false);
      await loadSettings();
      await loadRuns({ silent: true });
    } catch (error) {
      console.error("Failed to save focus settings:", error);
      message.error(extractRequestError(error, t("focus.saveFailed")));
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async () => {
    setStartingRun(true);
    try {
      await api.runFocusNow();
      message.success(t("focus.runStarted"));
      await loadRuns({ silent: true });
    } catch (error) {
      console.error("Failed to start focus run:", error);
      message.error(extractRequestError(error, t("focus.runFailed")));
    } finally {
      setStartingRun(false);
    }
  };

  const handleCancelRun = async (runId: string) => {
    try {
      await api.cancelFocusRun(runId);
      message.success(t("focus.cancelRunSuccess"));
      await loadRuns({ silent: true });
      if (selectedRunId === runId) {
        await loadRunDetail(runId, { silent: true });
      }
    } catch (error) {
      console.error("Failed to cancel focus run:", error);
      message.error(extractRequestError(error, t("focus.cancelRunFailed")));
    }
  };

  const handleOpenNote = async (noteId: string) => {
    setNoteDetailOpen(true);
    setNoteDetailLoading(true);
    setDetailNote(null);
    try {
      const note = await api.getFocusNote(noteId);
      setDetailNote(note);
    } catch (error) {
      console.error("Failed to load focus note detail:", error);
      message.error(t("focus.noteDetailLoadFailed"));
      setNoteDetailOpen(false);
    } finally {
      setNoteDetailLoading(false);
    }
  };

  const handleOpenRun = async (runId: string) => {
    setSelectedRunId(runId);
    setRunDetailOpen(true);
    setActiveRunTab("overview");
    setRunArchive(null);
    setRunDetail(null);
    await loadRunDetail(runId);
  };

  const runStatusOptions = useMemo(
    () => [
      { value: "all", label: t("focus.runsFilterAll") },
      { value: "running", label: t("focus.statusRunning") },
      { value: "completed", label: t("focus.statusCompleted") },
      { value: "failed", label: t("focus.statusFailed") },
      { value: "cancelled", label: t("focus.statusCancelled") },
      { value: "skipped", label: t("focus.statusSkipped") },
      { value: "timed_out", label: t("focus.statusTimedOut") },
    ],
    [t],
  );

  const getStatusTag = (status: FocusRunStatus) => {
    const map: Record<FocusRunStatus, { color: string; text: string }> = {
      running: { color: "blue", text: t("focus.statusRunning") },
      completed: { color: "green", text: t("focus.statusCompleted") },
      skipped: { color: "default", text: t("focus.statusSkipped") },
      timed_out: { color: "orange", text: t("focus.statusTimedOut") },
      failed: { color: "red", text: t("focus.statusFailed") },
      cancelled: { color: "default", text: t("focus.statusCancelled") },
    };
    const meta = map[status];
    return <Tag color={meta.color}>{meta.text}</Tag>;
  };

  const getTriggerTag = (triggerType: string) => {
    return (
      <Tag color="default">
        {triggerType === "scheduled"
          ? t("focus.triggerScheduled")
          : t("focus.triggerManual")}
      </Tag>
    );
  };

  const formatNotificationStatus = (status?: string | null) => {
    const map: Record<string, string> = {
      pending: t("focus.notificationPending"),
      sent: t("focus.notificationSent"),
      failed: t("focus.notificationFailed"),
      timeout: t("focus.notificationTimedOut"),
      cancelled: t("focus.notificationCancelled"),
      skipped_no_target: t("focus.notificationSkippedNoTarget"),
      skipped_no_notes: t("focus.notificationSkippedNoNotes"),
      not_applicable: t("focus.notificationNotApplicable"),
    };
    return map[status || "pending"] || status || t("focus.notificationPending");
  };

  const runTabItems = [
    { key: "overview", label: t("focus.runTabOverview") },
    { key: "notes", label: t("focus.runTabNotes") },
    { key: "prompt", label: t("focus.runTabPrompt") },
    { key: "output", label: t("focus.runTabOutput") },
    { key: "tools", label: t("focus.runTabTools") },
    { key: "notification", label: t("focus.runTabNotification") },
  ];

  const toolLogs = useMemo(() => normalizeToolLogs(runArchive), [runArchive]);
  const toolsUsed = useMemo(
    () => Array.from(new Set(toolLogs.map((log) => log.tool).filter(Boolean))),
    [toolLogs],
  );

  const renderMarkdownPanel = (content?: string | null, emptyText?: string) => {
    if (!content?.trim()) {
      return <Empty description={emptyText || t("focus.runArchivePending")} />;
    }

    return (
      <div className={styles.runMarkdownPanel}>
        <LazyMarkdown
          content={content}
          className={`${styles.noteMarkdown} ${styles.runMarkdownContent}`}
        />
      </div>
    );
  };

  const renderNotificationResult = () => {
    const result = runArchive?.notificationResult || {};
    const status =
      (typeof result.status === "string" ? result.status : undefined) ||
      runDetail?.notificationStatus ||
      "pending";
    const channel =
      typeof result.channel === "string" && result.channel
        ? result.channel
        : undefined;
    const error =
      typeof result.error === "string" && result.error ? result.error : undefined;

    const descriptionMap: Record<string, string> = {
      pending: t("focus.notificationDescriptionPending"),
      sent: channel
        ? t("focus.notificationDescriptionSentWithChannel", { channel })
        : t("focus.notificationDescriptionSent"),
      failed: error
        ? t("focus.notificationDescriptionFailedWithError", { error })
        : t("focus.notificationDescriptionFailed"),
      timeout: t("focus.notificationDescriptionTimedOut"),
      cancelled: t("focus.notificationDescriptionCancelled"),
      skipped_no_target: t("focus.notificationDescriptionSkippedNoTarget"),
      skipped_no_notes: t("focus.notificationDescriptionSkippedNoNotes"),
      not_applicable: t("focus.notificationDescriptionNotApplicable"),
    };

    const extraEntries = Object.entries(result).filter(
      ([key, value]) =>
        key !== "status" &&
        key !== "channel" &&
        key !== "error" &&
        value !== null &&
        value !== undefined &&
        value !== "",
    );

    return (
      <div className={styles.notificationTab}>
        <Card
          title={t("focus.notificationResultSummary")}
          size="small"
          className={styles.detailCard}
        >
          <div className={styles.notificationSummary}>
            <div>
              <div className={styles.overviewLabel}>
                {t("focus.notificationStatus")}
              </div>
              <div className={styles.notificationHeadline}>
                {formatNotificationStatus(status)}
              </div>
            </div>
            <p className={styles.notificationDescription}>
              {descriptionMap[status] ||
                t("focus.notificationDescriptionUnknown", {
                  status: formatNotificationStatus(status),
                })}
            </p>
            {channel ? (
              <div className={styles.notificationMetaLine}>
                <span className={styles.overviewLabel}>
                  {t("focus.notificationChannelLabel")}
                </span>
                <span>{channel}</span>
              </div>
            ) : null}
            {error ? (
              <div className={styles.notificationMetaLine}>
                <span className={styles.overviewLabel}>
                  {t("focus.notificationErrorLabel")}
                </span>
                <span>{error}</span>
              </div>
            ) : null}
          </div>
        </Card>

        {extraEntries.length > 0 ? (
          <Card
            title={t("focus.notificationExtraDetails")}
            size="small"
            className={styles.detailCard}
          >
            <pre className={styles.fileContent}>
              {renderJson(Object.fromEntries(extraEntries))}
            </pre>
          </Card>
        ) : null}
      </div>
    );
  };

  const initialLoading = settingsLoading && notesLoading && runsLoading;

  return (
    <div className={styles.focusPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{t("focus.title")}</h1>
          <p className={styles.description}>{t("focus.description")}</p>
        </div>
        <div className={styles.headerActions}>
          <Button onClick={refreshAll} className={styles.headerButton}>
            {t("common.refresh")}
          </Button>
          <Button
            onClick={handleRunNow}
            loading={startingRun}
            className={styles.headerButton}
          >
            {t("focus.executeNow")}
          </Button>
          <Button
            onClick={() => setRunsDrawerOpen(true)}
            className={styles.headerButton}
          >
            {t("focus.runsPanel")}
          </Button>
          <Button
            type="primary"
            onClick={() => setDrawerOpen(true)}
            className={styles.headerButton}
          >
            {t("focus.configure")}
          </Button>
        </div>
      </div>

      <div className={styles.contentGrid}>
        <div className={styles.noteColumn}>
          <Card className={styles.card}>
            <div className={styles.cardContent}>
              <div className={styles.toolbar}>
                <Input.Search
                  allowClear
                  value={searchKeyword}
                  onChange={(event) => setSearchKeyword(event.target.value)}
                  onSearch={(value) => setSearchKeyword(value)}
                  placeholder={t("focus.searchPlaceholder")}
                  className={styles.searchBox}
                />
                <span className={styles.metric}>
                  {t("common.total", { count: noteTotal })}
                </span>
              </div>

              {initialLoading || (notesLoading && notes.length === 0) ? (
                <div className={styles.state}>
                  <Spinner />
                </div>
              ) : notes.length === 0 ? (
                <div className={styles.emptyWrap}>
                  <Empty
                    description={
                      deferredSearchKeyword.trim()
                        ? t("focus.emptySearch")
                        : t("focus.emptyNotes")
                    }
                  />
                </div>
              ) : (
                <div className={styles.timeline}>
                  {notes.map((note) => (
                    <div key={note.id} className={styles.timelineItem}>
                      <div className={styles.timelineDot} />
                      <div className={styles.noteCard}>
                        <div className={styles.noteTop}>
                          <div>
                            <h3 className={styles.noteTitle}>{note.title}</h3>
                            <div className={styles.noteMeta}>
                              <span>{formatTimestamp(note.createdAt)}</span>
                              <span>
                                {t("focus.sourcePrefix", {
                                  source: note.source || t("focus.unknownSource"),
                                })}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className={styles.noteContent}>
                          <p className={styles.notePreview}>
                            {note.previewText || t("focus.emptyContent")}
                          </p>
                        </div>
                        <div className={styles.noteFooter}>
                          <Button
                            type="link"
                            className={styles.detailButton}
                            onClick={() => void handleOpenNote(note.id)}
                          >
                            {t("focus.viewDetails")}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!notesLoading && noteTotal > NOTE_PAGE_SIZE ? (
                <div className={styles.paginationBar}>
                  <Pagination
                    current={notePage}
                    pageSize={NOTE_PAGE_SIZE}
                    total={noteTotal}
                    showSizeChanger={false}
                    onChange={setNotePage}
                  />
                </div>
              ) : null}
            </div>
          </Card>
        </div>
      </div>

      <Drawer
        title={t("focus.runsTitle")}
        placement="right"
        open={runsDrawerOpen}
        onClose={() => setRunsDrawerOpen(false)}
        width={520}
      >
        <div className={styles.runsDrawerBody}>
          <div className={styles.sectionHeader}>
            <div>
              <p className={styles.sectionDescription}>{t("focus.runsDescription")}</p>
            </div>
            <div className={styles.sectionTools}>
              <Select
                value={runFilter}
                options={runStatusOptions}
                onChange={(value) => setRunFilter(value as RunFilterValue)}
                className={styles.runFilter}
              />
            </div>
          </div>

          <div className={styles.metricRow}>
            <span className={styles.metric}>
              {t("common.total", { count: runTotal })}
            </span>
          </div>

          {runsLoading && runs.length === 0 ? (
            <div className={styles.state}>
              <Spinner />
            </div>
          ) : runs.length === 0 ? (
            <div className={styles.emptyWrap}>
              <Empty description={t("focus.emptyRuns")} />
            </div>
          ) : (
            <div className={styles.runList}>
              {runs.map((run) => (
                <div
                  key={run.id}
                  className={`${styles.runItem} ${
                    run.status === "running" ? styles.runItemRunning : ""
                  }`}
                >
                  <div className={styles.runItemHeader}>
                    <div className={styles.runItemTags}>
                      {getStatusTag(run.status)}
                      {getTriggerTag(run.triggerType)}
                    </div>
                    <span className={styles.muted}>
                      {formatTimestamp(run.startedAt)}
                    </span>
                  </div>
                  <p className={styles.runSummary}>
                    {run.summary || t("focus.runSummaryEmpty")}
                  </p>
                  <div className={styles.runMeta}>
                    <span>{t("focus.noteCount", { count: run.noteCount })}</span>
                    <span>
                      {t("focus.notificationStatusLabel", {
                        value: formatNotificationStatus(run.notificationStatus),
                      })}
                    </span>
                  </div>
                  {run.tagSnapshot.length > 0 ? (
                    <div className={styles.tagList}>
                      {run.tagSnapshot.map((tag) => (
                        <Tag key={`${run.id}:${tag}`}>{tag}</Tag>
                      ))}
                    </div>
                  ) : null}
                  <div className={styles.runActions}>
                    <Button
                      type="link"
                      className={styles.detailButton}
                      onClick={() => void handleOpenRun(run.id)}
                    >
                      {t("focus.viewDetails")}
                    </Button>
                    {run.status === "running" ? (
                      <Popconfirm
                        title={t("focus.cancelRunTitle")}
                        description={t("focus.cancelRunConfirm")}
                        onConfirm={() => void handleCancelRun(run.id)}
                        okText={t("common.confirm")}
                        cancelText={t("common.cancel")}
                      >
                        <Button type="link" danger className={styles.detailButton}>
                          {t("focus.cancelRun")}
                        </Button>
                      </Popconfirm>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}

          {!runsLoading && runTotal > RUN_PAGE_SIZE ? (
            <div className={styles.paginationBar}>
              <Pagination
                current={runPage}
                pageSize={RUN_PAGE_SIZE}
                total={runTotal}
                showSizeChanger={false}
                onChange={setRunPage}
              />
            </div>
          ) : null}
        </div>
      </Drawer>

      <Drawer
        title={detailNote?.title || t("focus.noteDetails")}
        placement="right"
        open={noteDetailOpen}
        onClose={() => {
          setNoteDetailOpen(false);
          setDetailNote(null);
        }}
        width={760}
      >
        {noteDetailLoading ? (
          <div className={styles.state}>
            <Spinner />
          </div>
        ) : detailNote ? (
          <div className={styles.detailBody}>
            <div className={styles.detailMetaBlock}>
              <div className={styles.noteMeta}>
                <span>{formatTimestamp(detailNote.createdAt)}</span>
                <span>
                  {t("focus.sourcePrefix", {
                    source: detailNote.source || t("focus.unknownSource"),
                  })}
                </span>
              </div>
            </div>
            <div className={styles.detailMarkdownWrap}>
              <LazyMarkdown
                content={detailNote.content || ""}
                className={styles.noteMarkdown}
              />
            </div>
          </div>
        ) : (
          <Empty description={t("focus.emptyContent")} />
        )}
      </Drawer>

      <Drawer
        title={t("focus.runDetails")}
        placement="right"
        open={runDetailOpen}
        onClose={() => {
          setRunDetailOpen(false);
          setSelectedRunId(null);
          setRunDetail(null);
          setRunArchive(null);
          setActiveRunTab("overview");
        }}
        width={820}
      >
        {runDetailLoading ? (
          <div className={styles.state}>
            <Spinner />
          </div>
        ) : runDetail ? (
          <div className={styles.runDetailBody}>
            <div className={styles.runDetailHeader}>
              <div className={styles.runItemTags}>
                {getStatusTag(runDetail.status)}
                {getTriggerTag(runDetail.triggerType)}
              </div>
              {runDetail.status === "running" ? (
                <Popconfirm
                  title={t("focus.cancelRunTitle")}
                  description={t("focus.cancelRunConfirm")}
                  onConfirm={() => void handleCancelRun(runDetail.id)}
                  okText={t("common.confirm")}
                  cancelText={t("common.cancel")}
                >
                  <Button>{t("focus.cancelRun")}</Button>
                </Popconfirm>
              ) : null}
            </div>

            <div className={styles.tabsWrapper}>
              <Tabs
                activeKey={activeRunTab}
                onChange={(key) => setActiveRunTab(key as RunTabKey)}
                items={runTabItems}
              />
              {activeRunTab === "overview" ? (
                <div className={styles.runOverviewGrid}>
                  <div className={styles.overviewCard}>
                    <span className={styles.overviewLabel}>
                      {t("focus.startedAt")}
                    </span>
                    <span>{formatTimestamp(runDetail.startedAt)}</span>
                  </div>
                  <div className={styles.overviewCard}>
                    <span className={styles.overviewLabel}>
                      {t("focus.finishedAt")}
                    </span>
                    <span>{formatTimestamp(runDetail.finishedAt)}</span>
                  </div>
                  <div className={styles.overviewCard}>
                    <span className={styles.overviewLabel}>
                      {t("focus.noteCountLabel")}
                    </span>
                    <span>{runDetail.noteCount}</span>
                  </div>
                  <div className={styles.overviewCard}>
                    <span className={styles.overviewLabel}>
                      {t("focus.notificationStatus")}
                    </span>
                    <span>{formatNotificationStatus(runDetail.notificationStatus)}</span>
                  </div>
                  <div className={`${styles.overviewCard} ${styles.overviewCardWide}`}>
                    <span className={styles.overviewLabel}>{t("focus.summaryLabel")}</span>
                    <span>{runDetail.summary || t("focus.runSummaryEmpty")}</span>
                  </div>
                  {runDetail.reason ? (
                    <div className={`${styles.overviewCard} ${styles.overviewCardWide}`}>
                      <span className={styles.overviewLabel}>{t("focus.reasonLabel")}</span>
                      <span>{runDetail.reason}</span>
                    </div>
                  ) : null}
                  <div className={`${styles.overviewCard} ${styles.overviewCardWide}`}>
                    <span className={styles.overviewLabel}>
                      {t("focus.tagSnapshotLabel")}
                    </span>
                    <div className={styles.tagList}>
                      {runDetail.tagSnapshot.length > 0 ? (
                        runDetail.tagSnapshot.map((tag) => <Tag key={tag}>{tag}</Tag>)
                      ) : (
                        <span className={styles.muted}>{t("focus.noTags")}</span>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}

              {activeRunTab === "notes" ? (
                <div className={styles.generatedNotesList}>
                  {runDetail.generatedNotes.length > 0 ? (
                    runDetail.generatedNotes.map((note) => (
                      <div key={note.id} className={styles.generatedNoteCard}>
                        <div className={styles.generatedNoteTop}>
                          <h4 className={styles.generatedNoteTitle}>{note.title}</h4>
                          <span className={styles.muted}>
                            {formatTimestamp(note.createdAt)}
                          </span>
                        </div>
                        <p className={styles.generatedNotePreview}>
                          {note.previewText || t("focus.emptyContent")}
                        </p>
                        <div className={styles.runActions}>
                          <Button
                            type="link"
                            className={styles.detailButton}
                            onClick={() => void handleOpenNote(note.id)}
                          >
                            {t("focus.viewDetails")}
                          </Button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <Empty description={t("focus.emptyGeneratedNotes")} />
                  )}
                </div>
              ) : null}

              {activeRunTab === "prompt" ? (
                renderMarkdownPanel(runArchive?.prompt, t("focus.runArchivePending"))
              ) : null}

              {activeRunTab === "output" ? (
                renderMarkdownPanel(runArchive?.fullOutput, t("focus.runArchivePending"))
              ) : null}

              {activeRunTab === "tools" ? (
                runArchive ? (
                  <div className={styles.toolsTab}>
                    <Card
                      title={t("focus.toolUsageStats")}
                      size="small"
                      className={styles.detailCard}
                    >
                      <p>
                        {t("focus.toolCallCount")}
                        <Tag color="blue">{toolLogs.length}</Tag>
                      </p>
                      <p>{t("focus.toolsUsedLabel")}</p>
                      <div className={styles.tagList}>
                        {toolsUsed.length > 0 ? (
                          toolsUsed.map((tool) => <Tag key={tool}>{tool}</Tag>)
                        ) : (
                          <span className={styles.muted}>{t("focus.noToolLogs")}</span>
                        )}
                      </div>
                    </Card>

                    {toolLogs.length > 0 ? (
                      <Card
                        title={t("focus.toolLogDetails", { count: toolLogs.length })}
                        size="small"
                        className={styles.detailCard}
                      >
                        {toolLogs.map((log) => (
                          <div key={log.key} className={styles.toolLog}>
                            <div className={styles.toolLogHeader}>
                              <strong>{log.tool}</strong>
                              {log.callId ? <Tag>{log.callId}</Tag> : null}
                              <span>
                                {formatDisplayTime(log.timestamp) ||
                                  t("focus.timeUnknown")}
                              </span>
                            </div>
                            {log.args !== undefined && stringifyValue(log.args) ? (
                              <div className={styles.toolLogSection}>
                                <strong>{t("focus.toolArguments")}</strong>
                                <pre className={styles.fileContent}>
                                  {stringifyValue(log.args)}
                                </pre>
                              </div>
                            ) : null}
                            {log.result !== undefined && log.result !== null ? (
                              <div className={styles.toolLogSection}>
                                <strong>{t("focus.toolResultLabel")}</strong>
                                <pre className={styles.fileContent}>
                                  {stringifyValue(log.result)}
                                </pre>
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </Card>
                    ) : (
                      <Card
                        title={t("focus.runTabTools")}
                        size="small"
                        className={styles.detailCard}
                      >
                        <Empty description={t("focus.noToolLogs")} />
                      </Card>
                    )}
                  </div>
                ) : (
                  <Empty description={t("focus.runArchivePending")} />
                )
              ) : null}

              {activeRunTab === "notification" ? (
                renderNotificationResult()
              ) : null}
            </div>
          </div>
        ) : (
          <Empty description={t("focus.emptyRuns")} />
        )}
      </Drawer>

      <Drawer
        title={t("focus.configure")}
        placement="right"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={520}
        footer={
          <div className={styles.formActions}>
            <Button onClick={() => setDrawerOpen(false)}>{t("common.cancel")}</Button>
            <Button type="primary" loading={saving} onClick={() => form.submit()}>
              {t("common.save")}
            </Button>
          </div>
        }
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          initialValues={{
            enabled: false,
            everyNumber: 6,
            everyUnit: "h",
            notificationChannel: "last",
            tags: [],
            useDoNotDisturb: false,
            doNotDisturbStart: "23:00",
            doNotDisturbEnd: "08:00",
          }}
        >
          <Form.Item name="enabled" label={t("focus.enabled")} valuePropName="checked">
            <Switch />
          </Form.Item>

          <Form.Item label={t("focus.interval")} required className={styles.everyField}>
            <div className={styles.everyRow}>
              <Form.Item
                name="everyNumber"
                rules={[
                  { required: true, message: t("focus.intervalRequired") },
                  { type: "number", min: 1, message: t("focus.intervalMin") },
                ]}
                noStyle
              >
                <InputNumber min={1} className={styles.everyNumber} />
              </Form.Item>
              <Form.Item name="everyUnit" noStyle>
                <Select
                  options={EVERY_UNIT_OPTIONS.map((item) => ({
                    value: item.value,
                    label: t(item.labelKey),
                  }))}
                  className={styles.everyUnit}
                />
              </Form.Item>
            </div>
          </Form.Item>

          <Form.Item name="notificationChannel" label={t("focus.notificationChannel")}>
            <Select options={notificationOptions} />
          </Form.Item>

          <Form.Item name="tags" label={t("focus.tags")} extra={t("focus.tagsHelp")}>
            <Select
              mode="tags"
              tokenSeparators={[","]}
              placeholder={t("focus.tagsPlaceholder")}
              options={tags.map((tag) => ({ label: tag, value: tag }))}
            />
          </Form.Item>

          <Form.Item
            name="useDoNotDisturb"
            label={t("focus.doNotDisturb")}
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prev, cur) => prev.useDoNotDisturb !== cur.useDoNotDisturb}
          >
            {({ getFieldValue }) =>
              getFieldValue("useDoNotDisturb") ? (
                <div className={styles.timeRange}>
                  <Form.Item
                    name="doNotDisturbStart"
                    label={t("focus.doNotDisturbStart")}
                  >
                    <TimePickerHHmm />
                  </Form.Item>
                  <Form.Item name="doNotDisturbEnd" label={t("focus.doNotDisturbEnd")}>
                    <TimePickerHHmm />
                  </Form.Item>
                </div>
              ) : null
            }
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  );
}
