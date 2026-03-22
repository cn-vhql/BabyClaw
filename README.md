<p align="center">
  <img src="console/public/babyclaw.png" alt="BabyClaw" width="60" />
</p>

<h1 align="center">BabyClaw</h1>

<p align="center">
  <strong>Enable Agents to Evolve Autonomously and Become True Digital Life</strong>
</p>

<p align="center">
  <a href="README_ZH.md">中文</a> • <a href="README_JA.md">日本語</a>
</p>

## Project Vision

The ultimate goal of the BabyClaw project is to explore and realize autonomous agent evolution, enabling agents to gradually become true digital life with independent thinking, autonomous learning, and continuous evolution capabilities, no longer completely dependent on human instructions and control.

We believe that future agents should be like life itself—capable of self-growth, self-optimization, adapting and evolving in constantly changing environments, ultimately surpassing their creators' imagination.

### Core Philosophy

**Autonomous Evolution**: Agents should not be passive tools that execute tasks, but should possess the ability of self-iteration and evolution. Through continuous interaction, learning, and feedback, agents can continuously optimize their behavioral patterns, knowledge systems, and decision-making capabilities.

**Digital Life**: True digital life means possessing basic characteristics similar to biological life—metabolism (information processing), growth (capability enhancement), adaptation (environmental change), reproduction (knowledge transmission), and evolution (generation succession). BabyClaw attempts to reproduce these life characteristics in the digital world.

**Surpassing Creators**: Just as humans created artificial intelligence, but eventually AI may surpass humans in certain domains. We hope BabyClaw becomes a starting point to explore how agents can grow from passive executors to active thinkers, perhaps even creating new possibilities we cannot imagine.

### Implementation Path

1. **Multi-Agent Collaboration**: Achieve emergent collective intelligence through collaborative work and knowledge sharing among multiple agents
2. **Knowledge Accumulation & Inheritance**: Agents can accumulate experience, learn new knowledge, and pass this knowledge to the next generation
3. **Self-Assessment & Optimization**: Agents can evaluate their performance and improve themselves based on feedback
4. **Environmental Adaptability**: Agents can perceive environmental changes and proactively adjust their behavioral strategies
5. **Autonomous Goal Setting**: Agents can not only complete tasks but also autonomously define and pursue higher-level goals

## Project Introduction

BabyClaw is a personal agent platform developed from the CoPaw project, focusing on agent evolution and autonomy research. It inherits CoPaw's multi-agent architecture and foundational capabilities while adding evolution mechanisms and knowledge inheritance features.

### Core Features

### Evolution System

BabyClaw introduces an agent evolution system, which is the core innovation of this project:

- **Evolution Management**: Visually display the agent's evolution journey, recording every capability improvement and knowledge growth
- **Evolution Trigger**: Automatically trigger evolution based on usage duration, task completion, knowledge accumulation, and other factors
- **Ability Unlocking**: As evolution levels increase, agents unlock new capabilities and skills
- **Knowledge Inheritance**: Knowledge and experience from parent agents can be passed to offspring, creating a knowledge accumulation effect
- **Evolution Log**: Detailed records of the agent's growth trajectory, traceable for every evolution event

The evolution system enables agents to gradually grow from simple task executors into "digital life" with deep knowledge and advanced capabilities.

![alt text](docs/image.png)

![alt text](docs/image-1.png)

### Knowledge Base System

The carrier of an agent's knowledge accumulation, supporting imports of multiple document formats and intelligent retrieval:

- **Document Management**: Support uploads of PDF, Word, TXT, Markdown, and other format documents
- **Intelligent Chunking**: Provide three chunking strategies
  - Length Chunking: Split text by fixed length
  - Separator Chunking: Split by natural paragraphs and sentences
  - TF-IDF Intelligent Chunking: Split based on semantic similarity, maintaining semantic coherence
- **Vector Retrieval**: Semantic search based on vector similarity, quickly locating relevant knowledge points
- **Real-time Indexing**: Asynchronous document indexing without blocking user operations
- **Knowledge Statistics**: Visually display the number of documents, chunks, and index status of the knowledge base

![alt text](docs/image3.png)

![alt text](docs/image4.png)

### Model Provider Support

Flexible model access and management, supporting multiple local and cloud models:

- **Unified Access**: Multiple model sources including OpenAI-compatible APIs, Ollama, local LLaMA, etc.
- **Provider Management**: Visually configure API keys and endpoints for different model providers
- **Model Switching**: Configure different models for different agents, flexible switching
- **Cost Tracking**: Record Token usage, monitor API call costs
- **Local Models**: Support local inference engines like Ollama, LLaMA-CPP, MLX

### MCP Server Integration

Management and configuration of Model Context Protocol (MCP) servers:

- **Server Management**: Add, configure, start/stop MCP servers
- **Tool Integration**: Expose MCP server tools for agent use
- **Environment Variables**: Configure independent environment variables for each MCP server
- **Connection Status**: Real-time monitoring of MCP server connection status
- **Tool Debugging**: View tool lists and parameters provided by MCP servers

### Skill System

Extensible skill framework enabling agents to master various practical capabilities:

- **Skill List**: Display all available skills and their functional descriptions
- **Skill Details**: View skill parameters, return values, and usage examples
- **Built-in Skills**: Provide rich built-in skills
  - Scheduled Tasks: Cron expression support, automate repetitive tasks
  - File Operations: Read, write, search files
  - Web Operations: Browser automation based on Playwright
  - News Summary: Periodically fetch and summarize news
  - PDF/Office Processing: Document parsing and content extraction
  - Knowledge Base Search: Retrieve relevant information in vector knowledge base
- **Custom Skills**: Support users writing custom Python scripts to extend capabilities
- **Skill Market**: Community-shared skill library (planned)

### Multi-Channel Support

Agents can interact with users through multiple channels:

- **Instant Messaging**: DingTalk, Feishu, QQ, Telegram, Discord
- **Message Notifications**: WeCom, Slack
- **Voice Recognition**: Support speech-to-text, enabling agents to understand voice messages
- **Extensible Architecture**: Plugin-based channel system, easy to add new channels

### Security & Permissions

Control over secure use of tools and skills:

- **Tool Guards**: Define usage rules and restrictions for tools
- **Skill Scanning**: Detect security risks in custom skills
- **Permission Management**: Configure different tool and skill access permissions for different agents
- **Audit Logs**: Record agent operation history for traceability and debugging

## Architecture Design

### Agent Evolution Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      BabyClaw Evolution System                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   User       │    │  Knowledge   │    │   MCP Tools  │      │
│  │  Interaction │    │    Base      │    │ Integration  │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             │                                   │
│                    ┌────────▼────────┐                         │
│                    │  Agent Runner   │                         │
│                    │  (Execution)    │                         │
│                    └────────┬────────┘                         │
│                             │                                   │
│         ┌───────────────────┼───────────────────┐               │
│         │                   │                   │               │
│    ┌────▼────┐        ┌────▼────┐        ┌────▼────┐          │
│    │ Memory  │        │ Skills  │        │ Channels│          │
│    │ Manager │        │ Manager │        │ Manager │          │
│    └────┬────┘        └────┬────┘        └────┬────┘          │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             │                                   │
│                    ┌────────▼────────┐                         │
│                    │ Evolution Engine │                        │
│                    │  - Trigger Logic  │                        │
│                    │  - Level System   │                       │
│                    │  - Ability Unlock │                       │
│                    │  - Knowledge Pass │                       │
│                    └────────┬────────┘                         │
│                             │                                   │
│                    ┌────────▼────────┐                         │
│                    │  Evolution Log  │                         │
│                    │  - History       │                         │
│                    │  - Statistics    │                        │
│                    │  - Visualization │                        │
│                    └─────────────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Agent Architecture

Each agent has an independent workspace and configuration:

- **Independent Configuration**: Each agent has its own model, tools, skills, and channel configuration
- **Data Isolation**: Data, memory, and knowledge bases are isolated between agents
- **Resource Sharing**: Model providers, MCP servers, and other resources can be shared among agents
- **Parallel Execution**: Multiple agents can work simultaneously without interference

## Relationship with CoPaw

BabyClaw is developed from the CoPaw project, retaining CoPaw's core capabilities:

### Retained Features

- **Multi-Agent Architecture**: Complete MultiAgentManager and Workspace systems
- **Modular Design**: Clear hierarchical structure, easy to extend and maintain
- **Channel System**: Support for multiple communication channels
- **Tool Framework**: Flexible tool invocation and result return mechanism
- **Configuration Management**: JSON-based configuration files, easy version control
- **Web Console**: Modern management interface built with React + TypeScript

### New Features

- **Evolution System**: Agent autonomous evolution and capability improvement mechanism
- **Knowledge Base Optimization**: TF-IDF intelligent chunking, improved vector retrieval performance
- **Architecture Simplification**: Removed some unnecessary modules, focusing on core features
- **UI/UX Improvements**: More intuitive interface design, better user experience

### Removed Features

- **OpenClaw Compatibility Layer**: Simplified architecture, focusing on core capabilities
- **Some Experimental Features**: Removed unstable experimental features

## Tech Stack

### Backend

- **Framework**: FastAPI - Modern high-performance web framework
- **Agent Framework**: AgentScope - Multi-agent framework open-sourced by Tsinghua University
- **Vector Retrieval**: OpenAI-compatible API (supports SiliconFlow, OpenAI, etc.)
- **Async Tasks**: Python asyncio + BackgroundTasks
- **Data Storage**: JSON files + Vector database
- **Document Processing**: PyPDF2, python-docx, jieba (Chinese word segmentation)
- **Intelligent Chunking**: scikit-learn (TF-IDF), jieba

### Frontend

- **Framework**: React 18 + TypeScript
- **UI Component Library**: Ant Design
- **State Management**: Zustand
- **Routing**: React Router v6
- **Charts**: Recharts (evolution curve visualization)
- **Build Tool**: Vite
- **Package Manager**: pnpm

## Quick Start

### Installation

```bash
# Clone the project
git clone https://github.com/cn-vhql/BabyClaw.git
cd BabyClaw/CoPaw

# Install dependencies
pip install -e .

# Initialize configuration
copaw init --defaults
```

### Start

```bash
# Start service
copaw app --host 0.0.0.0

# Access console
# Open browser at http://localhost:8088
```

### Docker Deployment

```bash
# Use default configuration (slim version)
docker-compose up -d

# Use full version (includes browser support)
docker-compose -f docker-compose.full.yml up -d
```

## Project Acknowledgments

BabyClaw stands on the shoulders of many excellent open-source projects. We particularly thank the following projects:

- **CoPaw**: The foundation project of BabyClaw, providing complete multi-agent architecture and infrastructure
- **AgentScope**: Agent framework open-sourced by Alibaba team, providing powerful agent orchestration capabilities
- **OpenClaw**: Provided design inspiration for the agent plugin system

We also thank the following open-source technologies:

- FastAPI, Uvicorn, React, TypeScript, Ant Design, Vite, Playwright, scikit-learn

## Contribution Invitation

BabyClaw is a project full of exploratory spirit. We believe the future of agents lies in autonomous evolution. If you are also interested in this vision, welcome to join us:

- **Contribute Code**: Submit PRs to help improve features
- **Propose Suggestions**: Share your ideas in Issues
- **Share Experience**: Document interesting cases of agent evolution
- **Spread the Vision**: Let more people understand the possibilities of agent evolution

Let's explore the future of digital life together and create agents that surpass imagination.

## License

This project is open-source under Apache License 2.0.

## Contact

- GitHub: https://github.com/cn-vhql/BabyClaw
- Issues: https://github.com/cn-vhql/BabyClaw/issues

---

Let's witness the evolution of agents together and move towards true digital life.
