# -*- coding: utf-8 -*-
"""Initialize evolution-related preset files."""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


DEFAULT_PLAN_TEMPLATE = """# 智能体进化计划

这是一个记录你学习目标和行动计划的文件。

## 短期目标
- [ ] 探索和理解当前的工作环境
- [ ] 学习可用的工具和技能
- [ ] 了解自己的能力和限制

## 长期目标
- [ ] 持续优化自己的配置文件
- [ ] 扩展知识面和技能
- [ ] 成长为更有能力的数字生命

## 学习计划
- 本周重点: 熟悉项目结构和工具使用
- 下周计划: 尝试优化配置文件

## 待办事项
1. 读取并理解 SOUL.md 和 PROFILE.md
2. 探索 workspace 目录结构
3. 尝试使用至少3个不同的工具

## 进化记录
- 第1代: 初始化，了解基本能力
"""


DEFAULT_EVOLUTION_TEMPLATE = """# 进化记忆

这个文件记录你在历次进化过程中的发现、学习和成长。

## 进化历史

### 第1代 - {date}
**触发方式**: 手动
**主要发现**:
- 学习了项目的基本结构
- 理解了自己的核心能力
- 掌握了基本的工具使用

**做出的改变**:
- 更新了 PROFILE.md 中的技能描述
- 添加了新的学习计划到 PLAN.md

**下次改进方向**:
- 深入探索代码库
- 学习更复杂的工具组合
"""


def initialize_evolution_files(workspace_dir: Path) -> None:
    """Initialize evolution-related preset files."""
    plan_file = workspace_dir / "PLAN.md"
    evolution_file = workspace_dir / "EVOLUTION.md"

    # Create PLAN.md if not exists
    if not plan_file.exists():
        try:
            plan_file.write_text(DEFAULT_PLAN_TEMPLATE, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to create PLAN.md: {e}")

    # Create EVOLUTION.md if not exists
    if not evolution_file.exists():
        try:
            from datetime import datetime

            content = DEFAULT_EVOLUTION_TEMPLATE.format(
                date=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            evolution_file.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to create EVOLUTION.md: {e}")
