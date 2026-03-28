import { useMemo, useState } from "react";
import { Dropdown } from "antd";
import {
  DownOutlined,
  CheckOutlined,
  BgColorsOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import {
  CHAT_THEME_KEYS,
  getChatTheme,
  type ChatThemeKey,
} from "../chatThemes";
import styles from "./index.module.less";

interface ChatThemeSelectorProps {
  value: ChatThemeKey;
  isDark: boolean;
  onChange: (theme: ChatThemeKey) => void;
}

export default function ChatThemeSelector(props: ChatThemeSelectorProps) {
  const { value, isDark, onChange } = props;
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const themes = useMemo(
    () =>
      CHAT_THEME_KEYS.map((key) => {
        const theme = getChatTheme(key, isDark);
        return {
          key,
          preview: theme.preview,
          label: t(`chat.themes.${key}`),
        };
      }),
    [isDark, t],
  );

  const activeTheme =
    themes.find((theme) => theme.key === value) ?? themes[0] ?? null;

  const dropdownContent = (
    <div className={styles.panel}>
      {themes.map((theme) => {
        const isActive = theme.key === value;

        return (
          <div
            key={theme.key}
            className={[
              styles.option,
              isActive ? styles.optionActive : "",
            ].join(" ")}
            onClick={() => {
              onChange(theme.key);
              setOpen(false);
            }}
          >
            <span
              className={styles.optionPreview}
              style={{ background: theme.preview }}
            />
            <span className={styles.optionLabel}>{theme.label}</span>
            {isActive ? <CheckOutlined className={styles.optionCheck} /> : null}
          </div>
        );
      })}
    </div>
  );

  if (!activeTheme) return null;

  return (
    <Dropdown
      open={open}
      onOpenChange={setOpen}
      dropdownRender={() => dropdownContent}
      trigger={["click"]}
      placement="bottomLeft"
      getPopupContainer={(node) => node.parentElement ?? document.body}
    >
      <button
        type="button"
        className={[styles.trigger, open ? styles.triggerActive : ""].join(" ")}
        aria-label={t("chat.themes.label")}
      >
        <span className={styles.triggerIcon}>
          <BgColorsOutlined />
        </span>
        <span
          className={styles.triggerPreview}
          style={{ background: activeTheme.preview }}
        />
        <span className={styles.triggerLabel}>{activeTheme.label}</span>
        <DownOutlined
          className={[
            styles.triggerArrow,
            open ? styles.triggerArrowOpen : "",
          ].join(" ")}
        />
      </button>
    </Dropdown>
  );
}
