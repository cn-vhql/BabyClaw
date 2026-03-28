# -*- coding: utf-8 -*-
"""Safe SSE transport for MCP HTTP clients.

This avoids the upstream async-generator shutdown issue in
`mcp.client.sse.sse_client`, which can raise task-bound cancel-scope errors
when the generator is closed from a different task during app shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import anyio
import httpx
import mcp.types as types
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from httpx_sse import EventSource
from httpx_sse._exceptions import SSEError
from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from mcp.shared.message import SessionMessage

logger = logging.getLogger(__name__)


def _extract_session_id_from_endpoint(endpoint_url: str) -> str | None:
    query_params = parse_qs(urlparse(endpoint_url).query)
    return (
        query_params.get("sessionId", [None])[0]
        or query_params.get("session_id", [None])[0]
    )


def _normalize_sse_headers(
    headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = dict(headers or {})
    normalized["Accept"] = "text/event-stream"
    normalized["Cache-Control"] = "no-store"
    return normalized


async def _safe_aclose(resource: Any) -> None:
    if resource is None or not hasattr(resource, "aclose"):
        return
    with suppress(Exception):
        await resource.aclose()


@asynccontextmanager
async def safe_sse_client(
    url: str,
    headers: dict[str, Any] | None = None,
    timeout: float = 5,
    sse_read_timeout: float = 60 * 5,
    httpx_client_factory: McpHttpClientFactory = create_mcp_http_client,
    auth: httpx.Auth | None = None,
    on_session_created: Callable[[str], None] | None = None,
):
    """A safer SSE client context for MCP.

    The public behavior matches `mcp.client.sse.sse_client`, but the internal
    lifecycle uses explicit asyncio tasks and direct HTTPX resource cleanup
    instead of nested async-generator context managers.
    """

    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    client_cm = None
    client = None
    response_cm = None
    response = None
    sse_reader_task: asyncio.Task | None = None
    post_writer_task: asyncio.Task | None = None
    endpoint_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

    try:
        client_cm = httpx_client_factory(
            headers=_normalize_sse_headers(headers),
            auth=auth,
            timeout=httpx.Timeout(timeout, read=sse_read_timeout),
        )
        client = await client_cm.__aenter__()

        response_cm = client.stream(
            "GET",
            url,
            headers=_normalize_sse_headers(headers),
        )
        response = await response_cm.__aenter__()
        response.raise_for_status()
        event_source = EventSource(response)

        async def sse_reader() -> None:
            try:
                async for sse in event_source.aiter_sse():
                    logger.debug("Received SSE event: %s", sse.event)
                    match sse.event:
                        case "endpoint":
                            endpoint_url = urljoin(url, sse.data)
                            url_parsed = urlparse(url)
                            endpoint_parsed = urlparse(endpoint_url)
                            if (
                                url_parsed.netloc != endpoint_parsed.netloc
                                or url_parsed.scheme != endpoint_parsed.scheme
                            ):
                                raise ValueError(
                                    "Endpoint origin does not match connection "
                                    f"origin: {endpoint_url}"
                                )

                            if on_session_created:
                                session_id = _extract_session_id_from_endpoint(
                                    endpoint_url
                                )
                                if session_id:
                                    on_session_created(session_id)

                            if not endpoint_future.done():
                                endpoint_future.set_result(endpoint_url)

                        case "message":
                            if not sse.data:
                                continue
                            try:
                                message = types.JSONRPCMessage.model_validate_json(
                                    sse.data
                                )
                            except Exception as exc:  # pragma: no cover
                                logger.exception("Error parsing server message")
                                await read_stream_writer.send(exc)
                                continue

                            await read_stream_writer.send(SessionMessage(message))
                        case _:
                            logger.warning("Unknown SSE event: %s", sse.event)
            except asyncio.CancelledError:
                raise
            except SSEError as exc:  # pragma: no cover
                logger.exception("Encountered SSE exception")
                if not endpoint_future.done():
                    endpoint_future.set_exception(exc)
                else:
                    await read_stream_writer.send(exc)
            except Exception as exc:  # pragma: no cover
                logger.exception("Error in sse_reader")
                if not endpoint_future.done():
                    endpoint_future.set_exception(exc)
                else:
                    await read_stream_writer.send(exc)
            finally:
                if not endpoint_future.done():
                    endpoint_future.set_exception(
                        RuntimeError("SSE endpoint was not received before close")
                    )
                await _safe_aclose(read_stream_writer)

        async def post_writer(endpoint_url: str) -> None:
            try:
                async for session_message in write_stream_reader:
                    response = await client.post(
                        endpoint_url,
                        json=session_message.message.model_dump(
                            by_alias=True,
                            mode="json",
                            exclude_none=True,
                        ),
                    )
                    response.raise_for_status()
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover
                logger.exception("Error in post_writer")

        sse_reader_task = asyncio.create_task(sse_reader())
        endpoint_url = await endpoint_future
        post_writer_task = asyncio.create_task(post_writer(endpoint_url))

        yield read_stream, write_stream
    finally:
        for task in (post_writer_task, sse_reader_task):
            if task is not None:
                task.cancel()

        for task in (post_writer_task, sse_reader_task):
            if task is None:
                continue
            with suppress(asyncio.CancelledError, Exception):
                await task

        await _safe_aclose(write_stream_reader)
        await _safe_aclose(write_stream)
        await _safe_aclose(read_stream)
        await _safe_aclose(read_stream_writer)

        if response_cm is not None:
            with suppress(Exception):
                await response_cm.__aexit__(None, None, None)
        elif response is not None:
            await _safe_aclose(response)

        if client_cm is not None:
            with suppress(Exception):
                await client_cm.__aexit__(None, None, None)
        elif client is not None:
            await _safe_aclose(client)
