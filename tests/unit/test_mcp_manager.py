# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import time
import unittest

from copaw.app.mcp.manager import MCPClientManager


class _FakeClient:
    def __init__(
        self,
        name: str,
        *,
        hang_on_close: bool = False,
        close_order: list[str] | None = None,
    ) -> None:
        self.name = name
        self.hang_on_close = hang_on_close
        self.close_order = close_order
        self.connect_calls = 0
        self.close_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    async def close(self) -> None:
        self.close_calls += 1
        if self.close_order is not None:
            self.close_order.append(self.name)
        if self.hang_on_close:
            await asyncio.Event().wait()


class MCPClientManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_all_uses_lifo_and_survives_hanging_close(self) -> None:
        close_order: list[str] = []
        manager = MCPClientManager(close_timeout=0.02)
        manager._clients = {
            "first": _FakeClient("first", close_order=close_order),
            "last": _FakeClient(
                "last",
                hang_on_close=True,
                close_order=close_order,
            ),
        }

        started = time.perf_counter()
        await manager.close_all()
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.5)
        self.assertEqual(close_order, ["last", "first"])
        self.assertEqual(manager._clients, {})

    async def test_remove_client_returns_after_close_timeout(self) -> None:
        manager = MCPClientManager(close_timeout=0.02)
        client = _FakeClient("hanging", hang_on_close=True)
        manager._clients["demo"] = client

        started = time.perf_counter()
        await manager.remove_client("demo")
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.5)
        self.assertEqual(client.close_calls, 1)
        self.assertNotIn("demo", manager._clients)

    async def test_replace_client_swaps_even_if_old_close_hangs(self) -> None:
        manager = MCPClientManager(close_timeout=0.02)
        old_client = _FakeClient("old", hang_on_close=True)
        new_client = _FakeClient("new")
        manager._clients["demo"] = old_client
        manager._build_client = lambda _: new_client  # type: ignore[method-assign]

        started = time.perf_counter()
        await manager.replace_client("demo", client_config=object(), timeout=0.1)
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.5)
        self.assertIs(manager._clients["demo"], new_client)
        self.assertEqual(new_client.connect_calls, 1)
        self.assertEqual(old_client.close_calls, 1)
