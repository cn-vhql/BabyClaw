import {
  Layout,
  Menu,
  Button,
  type MenuProps,
} from "antd";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  MessageSquare,
  Radio,
  Zap,
  MessageCircle,
  Wifi,
  UsersRound,
  CalendarClock,
  Activity,
  Sparkles,
  Briefcase,
  Cpu,
  Box,
  Globe,
  Settings,
  Shield,
  Plug,
  Wrench,
  Database,
  PanelLeftClose,
  PanelLeftOpen,
  BarChart3,
  Mic,
  Bot,
  LogOut,
  Info,
} from "lucide-react";
import { clearAuthToken } from "../api/config";
import { authApi } from "../api/modules/auth";
import styles from "./index.module.less";
import { useTheme } from "../contexts/ThemeContext";
import { DEFAULT_OPEN_KEYS, KEY_TO_PATH } from "./constants";

// ── Layout ────────────────────────────────────────────────────────────────

const { Sider } = Layout;

// ── Types ─────────────────────────────────────────────────────────────────

interface SidebarProps {
  selectedKey: string;
}

// ── Sidebar ───────────────────────────────────────────────────────────────

export default function Sidebar({ selectedKey }: SidebarProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { isDark } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>(DEFAULT_OPEN_KEYS);
  const [authEnabled, setAuthEnabled] = useState(false);

  // ── Effects ──────────────────────────────────────────────────────────────

  useEffect(() => {
    authApi
      .getStatus()
      .then((res) => setAuthEnabled(res.enabled))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!collapsed) setOpenKeys(DEFAULT_OPEN_KEYS);
  }, [collapsed]);

  // ── Menu items ────────────────────────────────────────────────────────────

  const menuItems: MenuProps["items"] = [
    {
      key: "chat-group",
      label: t("nav.chatGroup"),
      icon: <MessageSquare size={16} />,
      children: [
        {
          key: "chat",
          label: t("nav.chat"),
          icon: <MessageCircle size={16} />,
        },
        {
          key: "evolution",
          label: t("nav.evolution"),
          icon: <Sparkles size={16} />,
        },
      ],
    },
    {
      key: "control-group",
      label: t("nav.control"),
      icon: <Radio size={16} />,
      children: [
        { key: "channels", label: t("nav.channels"), icon: <Wifi size={16} /> },
        {
          key: "sessions",
          label: t("nav.sessions"),
          icon: <UsersRound size={16} />,
        },
        {
          key: "cron-jobs",
          label: t("nav.cronJobs"),
          icon: <CalendarClock size={16} />,
        },
        {
          key: "heartbeat",
          label: t("nav.heartbeat"),
          icon: <Activity size={16} />,
        },
      ],
    },
    {
      key: "agent-group",
      label: t("nav.agent"),
      icon: <Zap size={16} />,
      children: [
        {
          key: "workspace",
          label: t("nav.workspace"),
          icon: <Briefcase size={16} />,
        },
        { key: "skills", label: t("nav.skills"), icon: <Sparkles size={16} /> },
        { key: "tools", label: t("nav.tools"), icon: <Wrench size={16} /> },
        { key: "mcp", label: t("nav.mcp"), icon: <Plug size={16} /> },
        {
          key: "knowledge",
          label: t("nav.knowledge"),
          icon: <Database size={16} />,
        },
        {
          key: "agent-config",
          label: t("nav.agentConfig"),
          icon: <Settings size={16} />,
        },
      ],
    },
    {
      key: "settings-group",
      label: t("nav.settings"),
      icon: <Cpu size={16} />,
      children: [
        { key: "agents", label: t("nav.agents"), icon: <Bot size={16} /> },
        { key: "models", label: t("nav.models"), icon: <Box size={16} /> },
        {
          key: "environments",
          label: t("nav.environments"),
          icon: <Globe size={16} />,
        },
        {
          key: "security",
          label: t("nav.security"),
          icon: <Shield size={16} />,
        },
        {
          key: "token-usage",
          label: t("nav.tokenUsage"),
          icon: <BarChart3 size={16} />,
        },
        {
          key: "voice-transcription",
          label: t("nav.voiceTranscription"),
          icon: <Mic size={16} />,
        },
        { key: "about", label: t("nav.about"), icon: <Info size={16} /> },
      ],
    },
  ];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <Sider
      collapsed={collapsed}
      onCollapse={setCollapsed}
      width={275}
      className={`${styles.sider}${isDark ? ` ${styles.siderDark}` : ""}`}
    >
      <div className={styles.siderTop}>
        {!collapsed && (
          <div className={styles.logoWrapper}>
            <img src="/babyclaw.png" alt="BabyClaw" style={{ height: 32, width: 'auto', marginRight: 8 }} />
            <h1 className={styles.logoText}>
              <span className={styles.logoTextBaby}>Baby</span>
              <span className={styles.logoTextClaw}>Claw</span>
            </h1>
          </div>
        )}
        <Button
          type="text"
          icon={
            collapsed ? (
              <PanelLeftOpen size={20} />
            ) : (
              <PanelLeftClose size={20} />
            )
          }
          onClick={() => setCollapsed(!collapsed)}
          className={styles.collapseBtn}
        />
      </div>

      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        openKeys={openKeys}
        onOpenChange={(keys) => setOpenKeys(keys as string[])}
        onClick={({ key }) => {
          const path = KEY_TO_PATH[String(key)];
          if (path) navigate(path);
        }}
        items={menuItems}
        theme={isDark ? "dark" : "light"}
      />

      {authEnabled && (
        <div style={{ padding: "12px 16px", borderTop: "1px solid #f0f0f0" }}>
          <Button
            type="text"
            icon={<LogOut size={16} />}
            onClick={() => {
              clearAuthToken();
              window.location.href = "/login";
            }}
            block
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              justifyContent: collapsed ? "center" : "flex-start",
            }}
          >
            {!collapsed && t("login.logout")}
          </Button>
        </div>
      )}
    </Sider>
  );
}
