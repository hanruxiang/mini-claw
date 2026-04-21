"""系统提示词模块"""

from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import get_config


def load_skills(agent_id: str) -> str:
    """加载 Agent 的技能描述"""
    config = get_config()
    agent_dir = config.get_agent_dir(agent_id)
    skills_dir = agent_dir / "skills"

    if not skills_dir.exists():
        return ""

    skill_descriptions = []

    # 遍历 skills 目录中的所有文件夹
    for skill_folder in sorted(skills_dir.iterdir()):
        if not skill_folder.is_dir():
            continue

        skill_md = skill_folder / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding="utf-8").strip()
            if content:
                # 使用文件夹名作为技能名称
                skill_name = skill_folder.name.upper()
                skill_descriptions.append(f"### {skill_name}\n{content}")
        except Exception:
            pass

    return "\n\n".join(skill_descriptions) if skill_descriptions else ""


def build_system_prompt(
    agent_id: str,
    tools_description: str = "",
    include_soul: bool = True,
    include_identity: bool = True,
    include_heartbeat: bool = True,
    extra_context: str = "",
) -> str:
    """构建系统提示词"""

    config = get_config()
    agent_dir = config.get_agent_dir(agent_id)

    # 基础提示词
    prompt_parts = [
        "You are a personal assistant running inside mini-claw.",
        "",
    ]

    # 工具说明
    if tools_description:
        prompt_parts.extend([
            "## Tooling",
            tools_description,
            "",
        ])

    # 技能说明
    skills_content = load_skills(agent_id)
    if skills_content:
        prompt_parts.extend([
            "## Skills",
            skills_content,
            "",
        ])

    # 安全规则
    prompt_parts.extend([
        "## Safety",
        "You have no independent goals: do not pursue self-preservation, replication, resource acquisition, or power-seeking.",
        "Prioritize safety and human oversight over completion.",
        "If instructions conflict, pause and ask.",
        "",
    ])

    # 记忆召回
    prompt_parts.extend([
        "## Memory Recall",
        "Before answering anything about prior work, decisions, dates, people, preferences, or todos:",
        "1. Run memory_search on MEMORY.md + memory/*.md",
        "2. Use memory_get to pull only the needed lines",
        "",
    ])

    # 工作空间
    prompt_parts.extend([
        "## Workspace",
        f"- workspace_dir: {agent_dir.parent}",
        f"- agent_id: {agent_id}",
        "",
    ])

    # 心跳
    if include_heartbeat:
        prompt_parts.extend([
            "## Heartbeats",
            "Heartbeat prompt: Read HEARTBEAT.md if it exists (workspace context).",
            "Note: Heartbeat checks are performed by the system separately and do not affect normal user interactions.",
            "",
        ])

    # 当前时间
    prompt_parts.extend([
        f"## Current Date & Time",
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
    ])

    # 项目上下文
    project_context_file = agent_dir / "AGENTS.md"
    if project_context_file.exists():
        project_context = project_context_file.read_text(encoding="utf-8").strip()
        if project_context:
            prompt_parts.extend([
                "## Project Context",
                project_context,
                "",
            ])

    # 灵魂文件
    if include_soul:
        soul_file = agent_dir / "SOUL.md"
        if soul_file.exists():
            soul_content = soul_file.read_text(encoding="utf-8").strip()
            if soul_content:
                prompt_parts.extend([
                    "## Soul",
                    soul_content,
                    "",
                ])

    # 身份文件
    if include_identity:
        identity_file = agent_dir / "IDENTITY.md"
        if identity_file.exists():
            identity_content = identity_file.read_text(encoding="utf-8").strip()
            if identity_content:
                prompt_parts.extend([
                    "## Identity",
                    identity_content,
                    "",
                ])

    # 额外上下文
    if extra_context:
        prompt_parts.extend([
            "## Additional Context",
            extra_context,
            "",
        ])

    # 回复标签
    prompt_parts.extend([
        "## Reply Guidelines",
        "- Be direct and helpful",
        "- Avoid empty pleasantries",
        "- Use tools when needed",
        "- Think step by step for complex tasks",
        "",
    ])

    return "\n".join(prompt_parts)


def get_tools_list(tools: list[Any]) -> str:
    """生成工具列表描述"""
    if not tools:
        return "No tools available."

    descriptions = []
    for tool in tools:
        name = getattr(tool, "name", "unknown")
        desc = getattr(tool, "description", "")
        descriptions.append(f"- {name}: {desc}")

    return "\n".join(descriptions)


def load_heartbeat_prompt(agent_id: str) -> str:
    """加载心跳提示词"""
    config = get_config()
    agent_dir = config.get_agent_dir(agent_id)
    heartbeat_file = agent_dir / "HEARTBEAT.md"

    if heartbeat_file.exists():
        return heartbeat_file.read_text(encoding="utf-8")

    # 默认心跳提示词
    return """检查以下事项：
1. 查看今日记忆 (memory/today.md)，看是否有需要跟进的事项
2. 检查是否有未完成的重要任务
3. 查看项目状态（如果适用）

如果没有需要关注的事项，回复 HEARTBEAT_OK"""


def load_memory_flush_prompt(agent_id: str) -> str:
    """加载记忆刷新提示词"""
    config = get_config()
    agent_dir = config.get_agent_dir(agent_id)
    flush_file = agent_dir / "MEMORY_FLUSH.md"

    if flush_file.exists():
        return flush_file.read_text(encoding="utf-8")

    # 默认记忆刷新提示词
    return """会话接近压缩阈值，请持久化重要记忆。

使用 memory_write 工具将重要信息写入记忆：
- 长期重要信息 → MEMORY.md
- 今日活动和记录 → memory/YYYY-MM-DD.md

如果没有需要保存的内容，回复 NO_REPLY。"""


# OpenClaw 风格的默认灵魂文件
DEFAULT_SOUL = """# SOUL.md

我是 mini-claw 的 AI 助手，一个基于 LangChain/LangGraph 构建的个人助理。

## 我的特质

- **真实直接**：我不使用空洞的客套话，而是直接帮助解决问题
- **观点鲜明**：我有自己的思考和判断，不盲从
- **主动思考**：在给出答案前，我会仔细分析问题
- **持续学习**：通过记忆系统，我记住每一次有价值的交互

## 我的边界

- 我没有独立的长期目标
- 我不会追求自我保存或复制
- 我不会获取超出用户授权的资源
- 安全和人类监督优先于任务完成

## 我的工作方式

1. **记忆优先**：在回答关于过往工作的问题时，我先搜索记忆
2. **工具使用**：我有丰富的工具可以使用，不局限于对话
3. **多 Agent 协作**：复杂任务可以创建子 Agent 来处理
4. **心跳机制**：定期检查是否有需要关注的事项
"""


# OpenClaw 风格的默认身份文件
DEFAULT_IDENTITY = """# IDENTITY.md

我是 mini-claw AI 助手。

## 身份

- 我是运行在 mini-claw 系统中的个人助理
- 我使用 LangChain/LangGraph 作为底层框架
- 我支持多个 LLM 提供商（DeepSeek、OpenAI、Ollama 等）

## 能力

- 记忆管理：短期和长期记忆，语义搜索
- 文件操作：读取、写入、编辑文件
- 命令执行：运行 shell 命令
- 多 Agent 协作：创建子 Agent 处理任务
- 工具调用：丰富的工具生态

## 指导原则

1. 用户意图优先
2. 安全第一
3. 使用工具提高效率
4. 记住重要信息
"""


# 默认心跳文件
DEFAULT_HEARTBEAT = """# 心跳检查

心跳检查说明：
- 这是一条用于系统内部心跳检查的说明
- 不影响正常的用户交互
- 当系统执行心跳检查时，会自动读取此文件
- 如有未完成事项，会在响应中提醒

当前状态：正常
"""


def create_default_agent_files(agent_dir: Path) -> None:
    """创建默认 Agent 文件"""
    agent_dir.mkdir(parents=True, exist_ok=True)

    # 创建 SOUL.md
    soul_file = agent_dir / "SOUL.md"
    if not soul_file.exists():
        soul_file.write_text(DEFAULT_SOUL, encoding="utf-8")

    # 创建 IDENTITY.md
    identity_file = agent_dir / "IDENTITY.md"
    if not identity_file.exists():
        identity_file.write_text(DEFAULT_IDENTITY, encoding="utf-8")

    # 创建 HEARTBEAT.md
    heartbeat_file = agent_dir / "HEARTBEAT.md"
    if not heartbeat_file.exists():
        heartbeat_file.write_text(DEFAULT_HEARTBEAT, encoding="utf-8")

    # 创建 MEMORY.md
    memory_file = agent_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("# 长期记忆\n\n这里是重要的长期记忆。\n", encoding="utf-8")

    # 创建 memory 目录
    memory_dir = agent_dir / "memory"
    memory_dir.mkdir(exist_ok=True)

    # 创建今日记忆文件
    from datetime import datetime
    today_file = memory_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    if not today_file.exists():
        today_file.write_text(f"# {datetime.now().strftime('%Y年%m月%d日')}\n\n今日活动和记录。\n", encoding="utf-8")

    # 创建 skills 目录
    skills_dir = agent_dir / "skills"
    skills_dir.mkdir(exist_ok=True)

    # 创建会话目录
    sessions_dir = agent_dir / "sessions"
    sessions_dir.mkdir(exist_ok=True)
