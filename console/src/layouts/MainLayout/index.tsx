import { Layout } from "antd";
import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Sidebar from "../Sidebar";
import Header from "../Header";
import ConsoleCronBubble from "../../components/ConsoleCronBubble";
import styles from "../index.module.less";

const { Content } = Layout;

const FocusPage = lazy(() => import("../../pages/Focus"));
const ChatPage = lazy(() => import("../../pages/Chat"));
const ChannelsPage = lazy(() => import("../../pages/Control/Channels"));
const SessionsPage = lazy(() => import("../../pages/Control/Sessions"));
const CronJobsPage = lazy(() => import("../../pages/Control/CronJobs"));
const HeartbeatPage = lazy(() => import("../../pages/Control/Heartbeat"));
const AgentConfigPage = lazy(() => import("../../pages/Agent/Config"));
const SkillsPage = lazy(() => import("../../pages/Agent/Skills"));
const ToolsPage = lazy(() => import("../../pages/Agent/Tools"));
const WorkspacePage = lazy(() => import("../../pages/Agent/Workspace"));
const MCPPage = lazy(() => import("../../pages/Agent/MCP"));
const KnowledgePage = lazy(() => import("../../pages/Agent/Knowledge"));
const EvolutionPage = lazy(() => import("../../pages/Agent/Evolution"));
const ModelsPage = lazy(() => import("../../pages/Settings/Models"));
const EnvironmentsPage = lazy(() => import("../../pages/Settings/Environments"));
const SecurityPage = lazy(() => import("../../pages/Settings/Security"));
const TokenUsagePage = lazy(() => import("../../pages/Settings/TokenUsage"));
const VoiceTranscriptionPage = lazy(
  () => import("../../pages/Settings/VoiceTranscription"),
);
const AgentsPage = lazy(() => import("../../pages/Settings/Agents"));
const AboutPage = lazy(() => import("../../pages/About"));

const pathToKey: Record<string, string> = {
  "/focus": "focus",
  "/chat": "chat",
  "/channels": "channels",
  "/sessions": "sessions",
  "/cron-jobs": "cron-jobs",
  "/heartbeat": "heartbeat",
  "/skills": "skills",
  "/tools": "tools",
  "/mcp": "mcp",
  "/workspace": "workspace",
  "/knowledge": "knowledge",
  "/evolution": "evolution",
  "/agents": "agents",
  "/models": "models",
  "/environments": "environments",
  "/agent-config": "agent-config",
  "/security": "security",
  "/token-usage": "token-usage",
  "/voice-transcription": "voice-transcription",
  "/about": "about",
};

function RouteLoadingFallback() {
  const { t } = useTranslation();

  return <div className={styles.routeLoading}>{t("common.loading")}</div>;
}

function renderLazyPage(
  PageComponent: LazyExoticComponent<ComponentType>,
) {
  return (
    <Suspense fallback={<RouteLoadingFallback />}>
      <PageComponent />
    </Suspense>
  );
}

export default function MainLayout() {
  const location = useLocation();
  const currentPath = location.pathname;
  const selectedKey = pathToKey[currentPath] || "chat";
  const isChatRoute = currentPath.startsWith("/chat");

  return (
    <Layout className={styles.mainLayout}>
      <Sidebar selectedKey={selectedKey} />
      <Layout>
        <Header selectedKey={selectedKey} />
        <Content className="page-container">
          <ConsoleCronBubble />
          <div
            className={`page-content ${isChatRoute ? styles.chatPageContent : ""}`}
          >
            <Routes>
              <Route path="/" element={<Navigate to="/chat" replace />} />
              <Route path="/focus" element={renderLazyPage(FocusPage)} />
              <Route path="/chat/*" element={renderLazyPage(ChatPage)} />
              <Route
                path="/channels"
                element={renderLazyPage(ChannelsPage)}
              />
              <Route
                path="/sessions"
                element={renderLazyPage(SessionsPage)}
              />
              <Route
                path="/cron-jobs"
                element={renderLazyPage(CronJobsPage)}
              />
              <Route
                path="/heartbeat"
                element={renderLazyPage(HeartbeatPage)}
              />
              <Route path="/skills" element={renderLazyPage(SkillsPage)} />
              <Route path="/tools" element={renderLazyPage(ToolsPage)} />
              <Route path="/mcp" element={renderLazyPage(MCPPage)} />
              <Route
                path="/workspace"
                element={renderLazyPage(WorkspacePage)}
              />
              <Route
                path="/knowledge"
                element={renderLazyPage(KnowledgePage)}
              />
              <Route
                path="/evolution"
                element={renderLazyPage(EvolutionPage)}
              />
              <Route path="/agents" element={renderLazyPage(AgentsPage)} />
              <Route path="/models" element={renderLazyPage(ModelsPage)} />
              <Route
                path="/environments"
                element={renderLazyPage(EnvironmentsPage)}
              />
              <Route
                path="/agent-config"
                element={renderLazyPage(AgentConfigPage)}
              />
              <Route path="/security" element={renderLazyPage(SecurityPage)} />
              <Route
                path="/token-usage"
                element={renderLazyPage(TokenUsagePage)}
              />
              <Route
                path="/voice-transcription"
                element={renderLazyPage(VoiceTranscriptionPage)}
              />
              <Route path="/about" element={renderLazyPage(AboutPage)} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
