# CoPaw Docker 版本说明

CoPaw 提供两套 Docker Compose 配置：

| 版本 | Compose 文件 | 浏览器支持 | 推荐内存 | 典型用途 |
|------|--------------|------------|----------|----------|
| Slim | `docker-compose.yml` / `docker-compose.slim.yml` | 否 | 1-2GB | 聊天、知识库、文件操作、定时任务 |
| Full | `docker-compose.full.yml` | 是 | 2-4GB | 网页访问、截图、浏览器自动化、可见浏览器调试 |

## 关键区别

- `slim` 不安装 Chromium、Xvfb、XFCE，镜像更小，常驻内存更低。
- `full` 会安装 Chromium 和桌面运行环境，适合 `browser_use`、网页截图和可见浏览器场景。
- 两个版本都会从当前源码目录本地构建镜像，不再依赖旧的 `BabyClaw` 镜像名。

## 启动方式

### Slim

```bash
docker compose up -d --build
```

或：

```bash
docker compose -f docker-compose.slim.yml up -d --build
```

### Full

```bash
docker compose -f docker-compose.full.yml up -d --build
```

## 默认镜像标签

- `slim`: `copaw:slim`
- `full`: `copaw:full`

可通过环境变量覆盖：

```bash
COPAW_IMAGE_TAG=my-copaw:dev docker compose up -d --build
```

## 常用环境变量

### 通用

- `COPAW_IMAGE_TAG`: 覆盖镜像标签
- `COPAW_CONTAINER_NAME`: 覆盖容器名，默认 `copaw`
- `COPAW_BIND_HOST`: 对外绑定地址，默认 `0.0.0.0`
- `COPAW_EXTERNAL_PORT`: 对外端口，默认 `8088`
- `COPAW_DISABLED_CHANNELS`: 默认 `imessage`
- `COPAW_APT_MIRROR`: APT 镜像，默认 `http://mirrors.tuna.tsinghua.edu.cn`
- `COPAW_NPM_REGISTRY`: npm 镜像，默认 `https://registry.npmmirror.com`
- `COPAW_PNPM_REGISTRY`: pnpm 镜像，默认 `https://registry.npmmirror.com`
- `COPAW_PIP_INDEX_URL`: pip 镜像，默认 `https://pypi.tuna.tsinghua.edu.cn/simple`
- `COPAW_PIP_TRUSTED_HOST`: pip 信任主机，默认 `pypi.tuna.tsinghua.edu.cn`
- `COPAW_UV_DEFAULT_INDEX`: uv 默认索引，默认 `https://pypi.tuna.tsinghua.edu.cn/simple`
- `COPAW_UV_INDEX_URL`: uv 兼容索引，默认 `https://pypi.tuna.tsinghua.edu.cn/simple`

### 资源限制

- `COPAW_MEM_LIMIT`
- `COPAW_MEM_RESERVATION`
- `COPAW_SHM_SIZE`

示例：

```bash
COPAW_APT_MIRROR=http://mirrors.tuna.tsinghua.edu.cn \
COPAW_NPM_REGISTRY=https://registry.npmmirror.com \
COPAW_PNPM_REGISTRY=https://registry.npmmirror.com \
COPAW_PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
COPAW_UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
COPAW_MEM_LIMIT=2g \
COPAW_MEM_RESERVATION=1g \
docker compose up -d --build
```

Full 版本建议：

```bash
COPAW_MEM_LIMIT=4g \
COPAW_MEM_RESERVATION=2g \
COPAW_SHM_SIZE=2g \
docker compose -f docker-compose.full.yml up -d --build
```

## 数据卷

默认会创建两个 Docker volume：

- `copaw-data`
- `copaw-secrets`

分别用于：

- 主工作目录 `/app/working`
- 敏感配置目录 `/app/working.secret`

## 健康检查

两个版本都使用：

```text
http://localhost:8088/health
```

## 何时选 Slim / Full

选择 `slim`：

- 只需要聊天和知识库
- 需要更低的内存占用
- 不依赖浏览器工具

选择 `full`：

- 需要让智能体真实访问网页
- 需要网页截图或浏览器自动化
- 需要可见浏览器进行演示或调试
