#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script for TF-IDF chunking strategy."""

import sys
sys.path.insert(0, 'src')

from copaw.agents.knowledge.chunk_strategies import chunk_text

# Sample text with multiple topics
SAMPLE_TEXT = """
人工智能技术发展迅速

机器学习是人工智能的一个重要分支。它通过算法让计算机从数据中学习规律。

深度学习是机器学习的子领域，使用神经网络模拟人脑的学习过程。

自然语言处理是AI的另一个重要应用领域。

大语言模型如GPT、BERT等在自然语言处理任务中表现出色。

计算机视觉是AI的又一重要分支。

图像识别、目标检测等技术已广泛应用于自动驾驶、医疗诊断等领域。

知识图谱是一种结构化的知识表示方式。

它将实体和关系以图的形式组织，有助于机器理解和推理知识。

强化学习让智能体通过与环境交互来学习最优策略。

AlphaGo就是强化学习的成功应用案例。
"""

def test_chunking_strategies():
    """Test all three chunking strategies and compare results."""

    print("=" * 80)
    print("测试三种分块策略的效果对比")
    print("=" * 80)
    print(f"原文长度: {len(SAMPLE_TEXT)} 字符")
    print()

    # Test 1: Length-based chunking
    print("\n【策略1: 固定长度分块】")
    print("-" * 80)
    chunks_length = chunk_text(
        text=SAMPLE_TEXT,
        doc_id="test",
        chunk_type="length",
        max_length=200,
        overlap=50
    )
    print(f"分块数量: {len(chunks_length)}")
    for i, chunk in enumerate(chunks_length[:3], 1):
        print(f"\n块 {i} ({len(chunk['content'])} 字符):")
        print(f"  {chunk['content'][:100]}...")

    # Test 2: Separator-based chunking
    print("\n\n【策略2: 分隔符分块】")
    print("-" * 80)
    chunks_separator = chunk_text(
        text=SAMPLE_TEXT,
        doc_id="test",
        chunk_type="separator",
        max_length=500,
        overlap=0,
        separators=["\n\n", "\n", "。"]
    )
    print(f"分块数量: {len(chunks_separator)}")
    for i, chunk in enumerate(chunks_separator[:3], 1):
        print(f"\n块 {i} ({len(chunk['content'])} 字符):")
        print(f"  {chunk['content'][:100]}...")

    # Test 3: TF-IDF chunking
    print("\n\n【策略3: TF-IDF 智能分块】")
    print("-" * 80)
    chunks_tfidf = chunk_text(
        text=SAMPLE_TEXT,
        doc_id="test",
        chunk_type="tfidf",
        max_length=300,
        overlap=30,
        separators=["\n\n", "\n"],
        min_similarity=0.2
    )
    print(f"分块数量: {len(chunks_tfidf)}")
    for i, chunk in enumerate(chunks_tfidf, 1):
        segment_count = chunk.get('segment_count', 'N/A')
        print(f"\n块 {i} ({len(chunk['content'])} 字符, {segment_count} 个段落):")
        # Show first 150 chars
        content_preview = chunk['content'][:150]
        print(f"  {content_preview}...")

    # Summary comparison
    print("\n\n【分块结果对比】")
    print("=" * 80)
    print(f"固定长度分块:  {len(chunks_length)} 个块")
    print(f"分隔符分块:    {len(chunks_separator)} 个块")
    print(f"TF-IDF 智能分块: {len(chunks_tfidf)} 个块")

    # Show TF-IDF chunk details
    print("\n\n【TF-IDF 分块详细分析】")
    print("-" * 80)
    for i, chunk in enumerate(chunks_tfidf, 1):
        segment_count = chunk.get('segment_count', 0)
        content = chunk['content']
        # Extract first sentence of each segment
        sentences = [s.strip() for s in content.split('。') if s.strip()][:3]
        summary = '。'.join(sentences)
        if summary and not summary.endswith('。'):
            summary += '。'
        print(f"\n块 {i}: {len(content)} 字符, {segment_count} 个段落")
        print(f"  内容摘要: {summary}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_chunking_strategies()
    except ImportError as e:
        print(f"错误: 缺少依赖库 {e}")
        print("\n请安装 scikit-learn:")
        print("  uv pip install scikit-learn")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
