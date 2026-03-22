# BabyClaw Docker镜像版本说明

BabyClaw提供两个Docker镜像版本，满足不同使用场景的需求。

## 版本对比

| 特性 | Slim版本 | Full版本 |
|------|---------|----------|
| **镜像大小** | ~800MB - 1.5GB | ~1.4GB - 2.1GB |
| **推荐内存** | 512MB - 2GB | 2GB - 4GB |
| **基础功能** | ✅ | ✅ |
| **对话功能** | ✅ | ✅ |
| **知识库** | ✅ | ✅ |
| **文件操作** | ✅ | ✅ |
| **定时任务** | ✅ | ✅ |
| **进化功能** | ✅ | ✅ |
| **MCP集成** | ✅ | ✅ |
| **IM频道** | ✅ | ✅ |
| **浏览器自动化** | ❌ | ✅ |
| **网页爬取** | ❌ | ✅ |
| **网页截图** | ❌ | ✅ |
| **可见浏览器** | ❌ | ✅ |

## Slim版本（推荐）

**镜像标签**: `agentscope/babyclaw:latest-slim`

### 适合场景
- 纯对话AI助理
- 知识库问答
- 文件管理和编辑
- 定时任务调度
- 数字生命进化
- 资源受限环境

### 不适合
- 需要访问网页
- 需要网页爬虫
- 需要浏览器自动化
- 需要网页截图

### 使用方法

#### Docker Compose
```bash
docker-compose up -d
```

#### Docker命令
```bash
docker run -d \
  --name babyclaw \
  -p 8088:8088 \
  -v babyclaw-data:/app/working \
  agentscope/babyclaw:latest-slim
```

### 配置说明

确保在`config.json`中禁用浏览器工具：

```json
{
  "tools": {
    "builtin_tools": {
      "browser_use": {
        "name": "browser_use",
        "enabled": false
      }
    }
  }
}
```

## Full版本

**镜像标签**: `agentscope/babyclaw:latest-full`

### 适合场景
- 需要网页爬取
- 需要浏览器自动化
- 需要网页截图
- 需要可见浏览器（演示、调试）
- 完整功能需求

### 使用方法

#### Docker Compose
```bash
docker-compose -f docker-compose.full.yml up -d
```

#### Docker命令
```bash
docker run -d \
  --name babyclaw \
  -p 8088:8088 \
  -v babyclaw-data:/app/working \
  --shm-size=2g \
  agentscope/babyclaw:latest-full
```

### 配置说明

浏览器工具已启用，可以直接使用：

```json
{
  "tools": {
    "builtin_tools": {
      "browser_use": {
        "name": "browser_use",
        "enabled": true
      }
    }
  }
}
```

## 构建镜像

从源代码构建：

```bash
# 构建两个版本
./build-docker.sh

# 只构建slim版本
./build-docker.sh --slim-only

# 只构建full版本
./build-docker.sh --full-only

# 自定义版本号
./build-docker.sh --version 1.0.0
```

手动构建：

```bash
# Slim版本
docker build \
  --build-arg INCLUDE_BROWSER=false \
  --tag babyclaw:latest-slim \
  --file deploy/Dockerfile .

# Full版本
docker build \
  --build-arg INCLUDE_BROWSER=true \
  --tag babyclaw:latest-full \
  --file deploy/Dockerfile .
```

## 资源使用建议

### Slim版本
- **最小内存**: 512MB
- **推荐内存**: 1-2GB
- **磁盘占用**: ~800MB - 1.5GB

### Full版本
- **最小内存**: 2GB
- **推荐内存**: 4GB
- **磁盘占用**: ~1.4GB - 2.1GB
- **额外要求**: `--shm-size=2g`（Chromium需要）

## 版本切换

如果需要从slim切换到full版本：

1. 停止并删除当前容器
   ```bash
   docker-compose down
   ```

2. 备份数据（可选，数据在volume中）
   ```bash
   docker run --rm -v babyclaw-data:/data -v $(pwd):/backup alpine \
     tar czf /backup/babyclaw-data-backup.tar.gz -C /data .
   ```

3. 使用full版本启动
   ```bash
   docker-compose -f docker-compose.full.yml up -d
   ```

4. 数据会自动保留（使用相同的volume）

## 故障排除

### Slim版本相关

**问题**: 智能体尝试使用浏览器功能
- **解决**: 在config.json中禁用browser_use工具

### Full版本相关

**问题**: 浏览器崩溃或无响应
- **解决**: 增加shm_size到2g或更多
- **解决**: 增加内存限制到4GB

**问题**: 容器启动缓慢
- **原因**: Chromium初始化需要时间
- **正常**: 启动时间可能需要30-60秒

## 性能优化

### 内存优化
```yaml
deploy:
  resources:
    limits:
      memory: 2G  # Slim版本
      memory: 4G  # Full版本
```

### 磁盘优化
- 使用slim版本可节省约650MB - 1GB磁盘空间
- 定期清理Docker未使用的镜像和容器
```bash
docker system prune -a
```

## 支持

- **文档**: https://copaw.agentscope.io/
- **GitHub**: https://github.com/agentscope-ai/CoPaw
- **Discord**: https://discord.gg/eYMpfnkG8h
