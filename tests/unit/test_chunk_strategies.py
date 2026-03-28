# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from copaw.agents.knowledge.chunk_strategies import chunk_text


class ChunkStrategiesTests(unittest.TestCase):
    def test_length_chunk_prefers_boundary_after_target_within_tolerance(self) -> None:
        text = ("A" * 85) + "\n" + ("B" * 20)

        chunks = chunk_text(
            text=text,
            doc_id="doc1",
            chunk_type="length",
            max_length=80,
            overlap=0,
        )

        self.assertEqual(chunks[0]["end"], 86)
        self.assertTrue(chunks[0]["content"].endswith("\n"))

    def test_length_chunk_prefers_boundary_before_target_within_tolerance(self) -> None:
        text = ("A" * 75) + "。" + ("B" * 20)

        chunks = chunk_text(
            text=text,
            doc_id="doc2",
            chunk_type="length",
            max_length=80,
            overlap=0,
        )

        self.assertEqual(chunks[0]["end"], 76)
        self.assertTrue(chunks[0]["content"].endswith("。"))

    def test_length_chunk_falls_back_to_fixed_split_without_boundary(self) -> None:
        text = ("A" * 120) + ("B" * 40)

        chunks = chunk_text(
            text=text,
            doc_id="doc3",
            chunk_type="length",
            max_length=80,
            overlap=0,
            separators=["\n\n", "\n"],
        )

        self.assertEqual(chunks[0]["end"], 80)
        self.assertEqual(len(chunks[0]["content"]), 80)


if __name__ == "__main__":
    unittest.main()
