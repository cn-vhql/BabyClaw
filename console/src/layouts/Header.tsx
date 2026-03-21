import { Layout, Space } from "antd";
import LanguageSwitcher from "../components/LanguageSwitcher";
import ThemeToggleButton from "../components/ThemeToggleButton";
import AgentSelector from "../components/AgentSelector";
import { useTranslation } from "react-i18next";
import styles from "./index.module.less";
import { KEY_TO_LABEL } from "./constants";

const { Header: AntHeader } = Layout;

interface HeaderProps {
  selectedKey: string;
}

export default function Header({ selectedKey }: HeaderProps) {
  const { t } = useTranslation();

  return (
    <AntHeader className={styles.header}>
      <span className={styles.headerTitle}>
        {t(KEY_TO_LABEL[selectedKey] || "nav.chat")}
      </span>
      <Space size="middle">
        <AgentSelector />
        <LanguageSwitcher />
        <ThemeToggleButton />
      </Space>
    </AntHeader>
  );
}
