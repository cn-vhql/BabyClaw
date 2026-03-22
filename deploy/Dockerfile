# -----------------------------------------------------------------------------
# Stage 1: build console frontend (dist not committed in repo).
# -----------------------------------------------------------------------------
FROM agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/node:slim AS console-builder
WORKDIR /app
# Install pnpm
RUN npm install -g pnpm
COPY console /app/console
RUN cd /app/console && pnpm install && pnpm run build

# -----------------------------------------------------------------------------
# Stage 2: runtime image with Python, optional Chromium, and app.
# -----------------------------------------------------------------------------
FROM agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/node:slim

# Build argument to control browser inclusion
# Set to "true" for full version with browser support, "false" for slim version
ARG INCLUDE_BROWSER=false

# ENV variables
ENV NODE_ENV=production
ENV WORKSPACE_DIR=/app
ENV COPAW_WORKING_DIR=/app/working
ENV COPAW_SECRET_DIR=/app/working.secret

# Channel filtering: use COPAW_DISABLED_CHANNELS (exclusion, recommended)
# or COPAW_ENABLED_CHANNELS (whitelist). Override at runtime with -e.
ARG COPAW_DISABLED_CHANNELS="imessage"
ENV COPAW_DISABLED_CHANNELS=${COPAW_DISABLED_CHANNELS}
ARG COPAW_ENABLED_CHANNELS=""
ENV COPAW_ENABLED_CHANNELS=${COPAW_ENABLED_CHANNELS}

ARG DEBIAN_FRONTEND=noninteractive

# Install base packages (always required)
RUN apt-get update && apt-get install -y --fix-missing \
    curl  \
    python3  \
    python3-pip  \
    python3-venv \
    build-essential  \
    libssl-dev  \
    git  \
    supervisor  \
    vim  \
    gettext-base \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean

# Install browser and GUI packages (only if INCLUDE_BROWSER=true)
RUN if [ "$INCLUDE_BROWSER" = "true" ]; then \
    apt-get update && apt-get install -y --fix-missing \
        xfce4 \
        xfce4-terminal \
        xvfb \
        dbus-x11 \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
        chromium \
        chromium-sandbox \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxtst6 \
        libnss3 \
        libglib2.0-0 \
        libdrm2 \
        libgbm1 \
        libasound2 \
        fonts-liberation \
        libu2f-udev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && sed -i 's/^CHROMIUM_FLAGS=""/CHROMIUM_FLAGS="--no-sandbox"/' /usr/bin/chromium; \
    fi

# Playwright configuration
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
# Indicate running in container (used e.g. for Chromium --no-sandbox).
ENV COPAW_RUNNING_IN_CONTAINER=1

# Set Playwright to use system Chromium only if browser is included
RUN if [ "$INCLUDE_BROWSER" = "true" ]; then \
    export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium; \
    fi

WORKDIR ${WORKSPACE_DIR}

RUN python3 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

COPY pyproject.toml setup.py README.md ./
COPY src ./src
# Inject console dist from build stage (repo does not commit dist).
COPY --from=console-builder /app/console/dist/ ./src/copaw/console/
# Install optional dependencies: ollama and knowledge (for TF-IDF chunking)
RUN pip install --no-cache-dir .[ollama,knowledge]

# Init working dir with default config.json and HEARTBEAT.md (build time).
RUN copaw init --defaults --accept-security

# CoPaw app port (default 8088). Override at runtime with -e COPAW_PORT=3000.
ENV COPAW_PORT=8088

COPY deploy/config/supervisord.conf.template /etc/supervisor/conf.d/supervisord.conf.template
COPY --chmod=755 deploy/entrypoint.sh /entrypoint.sh

EXPOSE 8088

CMD ["/entrypoint.sh"]
