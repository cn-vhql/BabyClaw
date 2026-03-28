#!/bin/sh
# Substitute COPAW_PORT in supervisord template and start supervisord.
# Default port 8088; override at runtime with -e COPAW_PORT=3000.
set -e
export COPAW_PORT="${COPAW_PORT:-8088}"
tmp_conf="/tmp/supervisord.rendered.conf.template"
cat /etc/supervisor/conf.d/supervisord.base.conf.template > "$tmp_conf"
if [ "${COPAW_INCLUDE_BROWSER:-false}" = "true" ]; then
  printf '\n' >> "$tmp_conf"
  cat /etc/supervisor/conf.d/supervisord.browser.conf.template >> "$tmp_conf"
fi
envsubst '${COPAW_PORT}' < "$tmp_conf" > /etc/supervisor/conf.d/supervisord.conf
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
