import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  message,
} from "@agentscope-ai/design";
import { Pagination, TimePicker } from "antd";
import dayjs from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import { Clock3, Tags } from "lucide-react";
import { useTranslation } from "react-i18next";

import api from "../../api";
import type { ChannelConfig } from "../../api/types";
import type {
  FocusNote,
  FocusRunResult,
  FocusSettings,
} from "../../api/types/focus";
import { LazyMarkdown } from "../../components/LazyMarkdown";
import {
  parseEvery,
  serializeEvery,
  type EveryUnit,
} from "../Control/Heartbeat/parseEvery";
import { useAgentStore } from "../../stores/agentStore";
import { stripFrontmatter } from "../../utils/markdown";
import styles from "./index.module.less";

dayjs.extend(customParseFormat);

const TIME_FORMAT = "HH:mm";
const NOTE_PAGE_SIZE = 10;

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

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return dayjs(date).format("YYYY-MM-DD HH:mm");
}

function toNotePreview(content: string) {
  return stripFrontmatter(content || "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^>\s?/gm, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/\|/g, " ")
    .replace(/[*_~]/g, "")
    .replace(/\r?\n+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export default function FocusPage() {
  const { t } = useTranslation();
  const { selectedAgent } = useAgentStore();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningNow, setRunningNow] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detailNote, setDetailNote] = useState<FocusNote | null>(null);
  const [settings, setSettings] = useState<FocusSettings | null>(null);
  const [notes, setNotes] = useState<FocusNote[]>([]);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [notificationOptions, setNotificationOptions] = useState<
    { label: string; value: string }[]
  >([]);
  const [form] = Form.useForm<FocusFormValues>();

  const loadPageData = async () => {
    setLoading(true);
    try {
      const [focusSettings, notesResult, channelConfigs] = await Promise.all([
        api.getFocusSettings(),
        api.listFocusNotes(),
        api.listChannels().catch(() => null),
      ]);

      setSettings(focusSettings);
      setNotes(notesResult.notes || []);

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
      console.error("Failed to load focus data:", error);
      message.error(t("focus.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPageData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent]);

  const filteredNotes = useMemo(() => {
    const keyword = searchKeyword.trim().toLowerCase();
    if (!keyword) {
      return notes;
    }

    return notes.filter((note) => {
      const haystack = [
        note.title,
        note.content,
        note.source,
        note.tags.join(" "),
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(keyword);
    });
  }, [notes, searchKeyword]);

  const pagedNotes = useMemo(() => {
    const start = (currentPage - 1) * NOTE_PAGE_SIZE;
    return filteredNotes.slice(start, start + NOTE_PAGE_SIZE);
  }, [currentPage, filteredNotes]);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchKeyword, selectedAgent]);

  useEffect(() => {
    const totalPages = Math.max(1, Math.ceil(filteredNotes.length / NOTE_PAGE_SIZE));
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, filteredNotes.length]);

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
      await loadPageData();
    } catch (error) {
      console.error("Failed to save focus settings:", error);
      message.error(t("focus.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const showRunResultMessage = (result: FocusRunResult) => {
    if (result.status === "skipped") {
      if (result.reason === "no_tags") {
        message.warning(t("focus.runSkippedNoTags"));
        return;
      }

      message.warning(t("focus.runSkipped"));
      return;
    }

    if (result.status === "timed_out") {
      message.warning(t("focus.runTimedOut"));
      return;
    }

    if (result.noteCount > 0) {
      message.success(t("focus.runSuccessWithNotes", { count: result.noteCount }));
      return;
    }

    message.success(t("focus.runSuccessNoChanges"));
  };

  const handleRunNow = async () => {
    setRunningNow(true);
    try {
      const result = await api.runFocusNow();
      if (result.status !== "skipped") {
        await loadPageData();
      }
      showRunResultMessage(result);
    } catch (error) {
      console.error("Failed to run focus now:", error);
      message.error(t("focus.runFailed"));
    } finally {
      setRunningNow(false);
    }
  };

  const tags = settings?.tags || [];

  return (
    <div className={styles.focusPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{t("focus.title")}</h1>
          <p className={styles.description}>{t("focus.description")}</p>
        </div>
        <div className={styles.headerActions}>
          <Button
            onClick={loadPageData}
            disabled={runningNow}
            className={styles.headerButton}
          >
            {t("common.refresh")}
          </Button>
          <Button
            onClick={handleRunNow}
            loading={runningNow}
            className={styles.headerButton}
          >
            {t("focus.executeNow")}
          </Button>
          <Button
            type="primary"
            onClick={() => setDrawerOpen(true)}
            disabled={runningNow}
            className={styles.headerButton}
          >
            {t("focus.configure")}
          </Button>
        </div>
      </div>

      <div className={styles.layout}>
        <div className={styles.timelineColumn}>
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
                  {t("common.total", { count: filteredNotes.length })}
                </span>
              </div>

              {loading ? (
                <div className={styles.state}>{t("common.loading")}</div>
              ) : filteredNotes.length === 0 ? (
                <div className={styles.emptyWrap}>
                  <Empty
                    description={
                      searchKeyword.trim()
                        ? t("focus.emptySearch")
                        : t("focus.emptyNotes")
                    }
                  />
                </div>
              ) : (
                <>
                  <div className={styles.timeline}>
                    {pagedNotes.map((note) => {
                      const fullContent = stripFrontmatter(note.content || "");
                      const previewContent = toNotePreview(note.content || "");

                      return (
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
                                {previewContent || t("focus.emptyContent")}
                              </p>
                            </div>
                            <div className={styles.noteFooter}>
                              <Button
                                type="link"
                                className={styles.detailButton}
                                onClick={() =>
                                  setDetailNote({
                                    ...note,
                                    content: fullContent,
                                  })
                                }
                              >
                                {t("focus.viewDetails")}
                              </Button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              {!loading && filteredNotes.length > 0 && (
                <div className={styles.paginationBar}>
                  <Pagination
                    current={currentPage}
                    pageSize={NOTE_PAGE_SIZE}
                    total={filteredNotes.length}
                    showSizeChanger={false}
                    onChange={setCurrentPage}
                  />
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      <Drawer
        title={detailNote?.title || t("focus.noteDetails")}
        placement="right"
        open={!!detailNote}
        onClose={() => setDetailNote(null)}
        width={760}
      >
        {detailNote ? (
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
        ) : null}
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

          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.useDoNotDisturb !== cur.useDoNotDisturb}>
            {({ getFieldValue }) =>
              getFieldValue("useDoNotDisturb") ? (
                <div className={styles.timeRange}>
                  <Form.Item name="doNotDisturbStart" label={t("focus.doNotDisturbStart")}>
                    <TimePickerHHmm />
                  </Form.Item>
                  <Form.Item name="doNotDisturbEnd" label={t("focus.doNotDisturbEnd")}>
                    <TimePickerHHmm />
                  </Form.Item>
                </div>
              ) : null
            }
          </Form.Item>

          <Card size="small" className={styles.drawerHint}>
            <div className={styles.hintTitleRow}>
              <Clock3 size={16} />
              <strong>{t("focus.behaviorTitle")}</strong>
            </div>
            <p>{t("focus.behaviorDescription")}</p>
            <div className={styles.hintTitleRow}>
              <Tags size={16} />
              <strong>{t("focus.notificationHintTitle")}</strong>
            </div>
            <p>{t("focus.notificationHint")}</p>
          </Card>
        </Form>
      </Drawer>
    </div>
  );
}
