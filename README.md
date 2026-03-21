<div align="center">

# BabyClaw

<p align="center">
  <img src="/babyclaw.png" alt="BabyClaw Logo" width="120">
</p>

<p align="center"><b>数字生命，伴你成长</b></p>

</div>

**BabyClaw** 是一款创新的AI个人助理平台，不仅提供智能对话能力，更支持**数字生命进化**——智能体能够自主探索、学习并自我进化，成为真正的数字生命。

---

## ✨ 核心特性

### 🧬 数字生命进化

BabyClaw 独创的**数字生命进化系统**让智能体突破传统对话框架：

- **自主进化**：智能体通过定时任务自动探索世界、更新自我认知，无需用户干预
- **完整记录**：详细记录每一代进化的变化（Soul、Profile、Plan的前后对比）
- **进化快照**：每轮进化的完整存档，支持回滚和历史查看
- **多维展示**：6个Tab详细展示进化的Soul、Profile、Plan、工具记录、输出和记忆
- **代数追踪**：清晰记录进化代数、触发方式（手动/定时/自动）和执行状态

### 🌐 多智能体架构

- **智能体隔离**：每个智能体拥有独立的配置、工作区、记忆和工具集
- **智能体切换器**：在多个智能体之间快速切换，满足不同场景需求
- **零停机重载**：修改配置后优雅加载，无需重启服务
- **独立数据**：每个智能体的记忆、技能、知识库完全隔离

### 💪 强大的技能系统

- **可视化编辑**：创建、编辑技能采用三字段结构（name、description、content），清晰直观
- **技能安全扫描**：自动检测技能中的危险操作和潜在风险
- **AI智能优化**：使用AI自动优化技能内容，提升技能质量
- **多平台导入**：支持从LobeHub、魔搭、GitHub、SkillsHub等平台导入技能
- **ZIP批量导入**：支持上传ZIP压缩包批量导入技能
- **实时同步**：编辑技能后自动同步到active环境，立即生效

### 🔌 MCP生态集成

- **MCP客户端管理**：可视化管理Model Context Protocol客户端
- **工具自动发现**：自动发现MCP服务提供的工具能力
- **流式连接**：基于SSE的实时流式连接，支持自动重连
- **连接测试**：一键测试MCP连接状态，查看可用工具

### 🧠 智能记忆系统

- **长期记忆**：基于ReMe的持久化记忆，支持向量检索和全文本搜索
- **知识库管理**：上传文档、自动分块、向量化存储
- **智能检索**：智能体可检索知识库内容，支持多种分块策略
- **记忆注入**：支持将记忆文件注入到系统提示词

### 📊 多端接入

- **即时通讯**：钉钉、飞书、QQ、Discord、Telegram等频道
- **企业微信**：支持企业微信应用和小艺接入
- **语音转写**：Whisper语音转文字，支持语音对话
- **AI卡片回复**：钉钉智能卡片式回复，提升交互体验

### 🎨 现代化控制台

- **响应式设计**：完美适配桌面和移动设备
- **主题切换**：支持暗色模式和亮色模式自由切换
- **多语言**：默认中文，支持英文、日文、俄文等多种语言
- **实时流式对话**：基于SSE的流式输出，支持重连和恢复
- **多模态对话**：支持图片查看和图像理解
- **会话管理**：完整的会话历史、收藏和导航功能

### ⏰ 强大的定时任务

- **Cron表达式**：支持标准Cron表达式，灵活配置定时规则
- **任务类型**：支持对话、进化等多种任务类型
- **时区选择**：自动识别时区，支持全球部署
- **任务管理**：查看任务执行历史、日志和状态

---

## 🚀 快速开始

### pip 安装

如果你习惯自行管理 Python 环境：

```bash
pip install copaw
copaw init --defaults
copaw app
```

在浏览器打开 **http://127.0.0.1:8088/** 即可使用控制台。

### 脚本安装

无需手动配置 Python，一行命令自动完成安装。

**macOS / Linux:**

```bash
curl -fsSL https://copaw.agentscope.io/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://copaw.agentscope.io/install.ps1 | iex
```

### Docker 部署

```bash
docker pull agentscope/copaw:latest
docker run -p 127.0.0.1:8088:8088 \
  -v copaw-data:/app/working \
  -v copaw-secrets:/app/working.secret \
  agentscope/copaw:latest
```

### 桌面应用

从 [GitHub Releases](https://github.com/agentscope-ai/CoPaw/releases) 下载桌面应用，双击即可运行，无需配置Python环境。

---

## 📖 主要功能

### 1. 数字对话

- **多模态输入**：支持文本、图片、语音等多种输入方式
- **流式输出**：实时的打字机效果，提升交互体验
- **会话历史**：完整保存对话历史，支持查看和恢复
- **消息操作**：支持复制、删除、收藏等操作
- **模型选择**：支持多种大模型，可随时切换

### 2. 智能体管理

- **创建智能体**：快速创建多个独立智能体
- **配置管理**：配置模型提供商、API Key、系统提示词等
- **智能体切换**：在不同智能体间快速切换
- **配置导入导出**：支持配置的批量导入导出

### 3. 进化管理

- **手动进化**：一键触发智能体进化
- **定时进化**：设置Cron定时任务，自动执行进化
- **进化历史**：查看所有进化记录和详情
- **进化对比**：对比进化前后的Soul、Profile、Plan变化
- **快照管理**：查看和管理进化快照

### 4. 技能管理

- **技能列表**：查看所有内置和自定义技能
- **创建技能**：使用YAML Frontmatter格式创建技能
- **编辑技能**：可视化编辑技能的name、description和content
- **删除技能**：支持删除不需要的自定义技能
- **启用/禁用**：灵活控制技能的启用状态
- **技能导入**：从多平台导入技能包

### 5. 知识库

- **创建知识库**：上传文档创建个人知识库
- **文档管理**：添加、删除知识库中的文档
- **分块策略**：支持固定长度、分隔符、智能分块策略
- **向量检索**：基于语义相似度的智能检索

### 6. MCP管理

- **添加客户端**：配置本地或远程MCP服务器
- **连接测试**：一键测试MCP连接状态
- **工具查看**：查看MCP提供的所有工具
- **客户端管理**：编辑、删除、启用/禁用MCP客户端

### 7. 定时任务

- **创建任务**：使用Cron表达式创建定时任务
- **任务类型**：对话任务、进化任务等
- **执行历史**：查看任务执行历史和日志
- **任务管理**：暂停、恢复、删除定时任务

### 8. 工作区管理

- **文件浏览**：可视化的工作区文件浏览器
- **文件编辑**：在线编辑工作区中的配置文件
- **核心文件**：快速访问SOUL.md、PROFILE.md、PLAN.md等核心文件
- **系统提示词配置**：可视化配置系统提示词

---

## 🔧 配置说明

### API Key 配置

首次使用前需要配置大模型API Key：

1. 打开控制台 → **设置** → **模型**
2. 选择提供商（DashScope、ModelScope、OpenAI等）
3. 填写API Key并启用提供商

### 智能体初始化

BabyClaw会自动创建三个预置文件：

- **SOUL.md**：智能体的核心信念、价值观和行为准则
- **PROFILE.md**：智能体的能力描述、专长和限制
- **PLAN.md**：智能体的学习计划、目标和待办事项

这些文件定义了智能体的"个性"，你可以在工作区管理中编辑它们。

### 记忆配置

- **长期记忆**：自动保存对话历史到本地
- **记忆检索**：智能体可检索历史对话内容
- **记忆上限**：可配置的记忆保存条数限制

---

## 💡 使用场景

### 个人助理

- **日程管理**：安排会议、提醒事项、管理待办
- **信息整理**：整理邮件、文档、联系人信息
- **知识问答**：基于个人知识库的问答

### 学习助手

- **课程总结**：自动总结课程内容和要点
- **知识复习**：定期提醒复习重点内容
- **学习计划**：制定和跟踪学习计划

### 创作助手

- **创意构思**：提供创意灵感和方向
- **内容生成**：辅助生成文章、脚本、代码
- **作品优化**：提供改进建议和优化

### 工作助手

- **文档处理**：阅读、摘要、翻译文档
- **数据分析**：分析数据、生成报告
- **自动化**：自动化重复性工作

---

## 🛠️ 技术栈

- **后端**：Python 3.10+、FastAPI、AgentScope
- **前端**：React 18、TypeScript、Ant Design
- **数据库**：Chroma向量数据库
- **记忆系统**：ReMe记忆框架
- **模型支持**：DashScope、ModelScope、OpenAI、Ollama等

---

## 📚 文档

完整文档请访问：[https://copaw.agentscope.io/](https://copaw.agentscope.io/)

- [快速开始](https://copaw.agentscope.io/docs/quickstart)
- [控制台使用](https://copaw.agentscope.io/docs/console)
- [智能体配置](https://copaw.agentscope.io/docs/config)
- [技能开发](https://copaw.agentscope.io/docs/skills)
- [MCP集成](https://copaw.agentscope.io/docs/mcp)
- [知识库管理](https://copaw.agentscope.io/docs/knowledge)
- [定时任务](https://copaw.agentscope.io/docs/cron)
- [常见问题](https://copaw.agentscope.io/docs/faq)

---

## 🤝 参与贡献

欢迎各种形式的参与！请阅读 [CONTRIBUTING](https://github.com/agentscope-ai/CoPaw/blob/main/CONTRIBUTING_zh.md) 了解如何开始。

我们特别欢迎：

- 新功能建议和实现
- Bug修复
- 文档改进
- 技能分享
- 测试反馈

---

## 📮 联系我们

| [Discord](https://discord.gg/eYMpfnkG8h)                                                                                                                                      | [X (Twitter)](https://x.com/agentscope_ai)                                                                                                | [钉钉](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)                                                                                                                                       |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [<img src="https://gw.alicdn.com/imgextra/i1/O1CN01hhD1mu1Dd3BWVUvxN_!!6000000000238-2-tps-400-400.png" width="80" height="80" alt="Discord">](https://discord.gg/eYMpfnkG8h) | [<img src="https://img.shields.io/badge/X-black.svg?logo=x&logoColor=white" width="80" height="80" alt="X">](https://x.com/agentscope_ai) | [<img src="https://img.alicdn.com/imgextra/i2/O1CN01vCWI8a1skHtLGXEMQ_!!6000000005804-2-tps-458-460.png" width="80" height="80" alt="钉钉">](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11) |

---

## 📄 许可证

BabyClaw 采用 [Apache License 2.0](LICENSE) 开源协议。

---

## 🙏 致谢

感谢以下开源项目的卓越贡献，BabyClaw 站在了巨人的肩膀上：

### 核心框架

- **[AgentScope](https://github.com/agentscope-ai/agentscope)** - 强大的多智能体框架
- **[AgentScope Runtime](https://github.com/agentscope-ai/agentscope-runtime)** - 高效的智能体运行时环境
- **[ReMe](https://github.com/agentscope-ai/ReMe)** - 智能记忆管理系统

### 技能生态

- **[OpenClaw Skills](https://github.com/openclaw-skills/cli-developer)** - 丰富的开源技能仓库，为BabyClaw提供多样化的能力扩展
- **[CoPaw](https://github.com/agentscope-ai/CoPaw)** - 本项目的上游框架，提供了坚实的基础架构和多智能体管理能力

### 社区贡献

感谢 [AgentScope 社区](https://github.com/agentscope-ai) 的所有贡献者，以及为技能生态、工具开发做出贡献的开发者们。

特别感谢：

- **[AgentScope 团队](https://github.com/agentscope-ai)** - 提供强大的框架支持
- **OpenClaw 社区** - 提供丰富的技能资源
- **所有 BabyClaw 的用户和反馈者** - 你们的建议和反馈让产品不断完善

---

<div align="center">

**让AI成为你生活中最默契的伙伴** 🐾

</div>
