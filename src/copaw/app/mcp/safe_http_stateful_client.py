# -*- coding: utf-8 -*-
"""Safer HTTP stateful MCP client variants for CoPaw."""

from __future__ import annotations

from contextlib import suppress
from typing import Any, Literal

from agentscope.mcp._stateful_client_base import StatefulClientBase
from mcp.client.streamable_http import streamablehttp_client

from .safe_sse import safe_sse_client


class SafeHttpStatefulClient(StatefulClientBase):
    """HTTP MCP client that uses a safer SSE transport implementation."""

    def __init__(
        self,
        name: str,
        transport: Literal["streamable_http", "sse"],
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30,
        sse_read_timeout: float = 60 * 5,
        **client_kwargs: Any,
    ) -> None:
        super().__init__(name=name)

        assert transport in ["streamable_http", "sse"]
        self.transport = transport

        if self.transport == "streamable_http":
            self.client = streamablehttp_client(
                url=url,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
                **client_kwargs,
            )
        else:
            self.client = safe_sse_client(
                url=url,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
                **client_kwargs,
            )

    async def close(self, ignore_errors: bool = True) -> None:
        """Close the client without routing through AsyncExitStack.aclose().

        Upstream `StatefulClientBase.close()` exits the transport and
        `ClientSession` via one `AsyncExitStack`, but MCP's `ClientSession`
        uses an anyio TaskGroup whose `__aexit__` may crash when close is
        executed from a different task. We only need best-effort shutdown here,
        so we close transport resources directly and cancel the session task
        group without awaiting its task-group exit path.
        """
        if not self.is_connected:
            raise RuntimeError(
                "The MCP server is not connected. Call connect() before closing.",
            )

        try:
            session = self.session
            if session is not None:
                exit_stack = getattr(session, "_exit_stack", None)
                if exit_stack is not None:
                    await exit_stack.aclose()

                task_group = getattr(session, "_task_group", None)
                if task_group is not None:
                    task_group.cancel_scope.cancel()

            if self.client is not None and hasattr(self.client, "__aexit__"):
                await self.client.__aexit__(None, None, None)
        except Exception as exc:
            if not ignore_errors:
                raise
            with suppress(Exception):
                task_group = getattr(self.session, "_task_group", None)
                if task_group is not None:
                    task_group.cancel_scope.cancel()
            from agentscope._logging import logger

            logger.warning("Error during MCP client cleanup: %s", exc)
        finally:
            self.stack = None
            self.session = None
            self.is_connected = False
