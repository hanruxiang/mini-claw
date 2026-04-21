"""命令执行工具"""

import subprocess
from pathlib import Path
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ExecInput(BaseModel):
    """exec 工具输入"""
    command: str = Field(description="要执行的命令")
    timeout: int | None = Field(default=30, description="超时时间（秒）")


class ExecTool(BaseTool):
    """执行 Shell 命令"""

    name: str = "exec"
    description: str = """执行 Shell 命令并返回输出。
支持常用命令如 ls, pwd, cat, grep, find, python, npm, git 等。
"""
    args_schema: type[BaseModel] = ExecInput

    allowed_commands: set[str] | None = None
    blocked_commands: set[str] = Field(
        default_factory=lambda: {
            "rm", "rmdir", "del", "format", "fdisk",
            "mkfs", "dd", "reboot", "shutdown", "halt",
            "chmod", "chown", "useradd", "userdel",
            "passwd", "su", "sudo",
        }
    )

    def _validate_command(self, command: str) -> tuple[bool, str]:
        """验证命令安全性"""
        # 获取基础命令
        parts = command.strip().split()
        if not parts:
            return False, "空命令"

        base_cmd = parts[0]

        # 检查阻止列表
        if base_cmd in self.blocked_commands:
            return False, f"命令不允许执行: {base_cmd}"

        # 检查允许列表（如果设置了）
        if self.allowed_commands and base_cmd not in self.allowed_commands:
            return False, f"命令不在允许列表中: {base_cmd}"

        return True, ""

    def _run(self, command: str, timeout: int | None = 30) -> str:
        # 验证命令
        valid, error = self._validate_command(command)
        if not valid:
            return error

        try:
            # 执行命令
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=None,  # 使用当前工作目录
            )

            output = []
            if result.stdout:
                output.append(result.stdout)
            if result.stderr:
                output.append(f"STDERR: {result.stderr}")
            if result.returncode != 0:
                output.append(f"退出码: {result.returncode}")

            return "\n".join(output) if output else "(无输出)"

        except subprocess.TimeoutExpired:
            return f"命令执行超时（{timeout}秒）"
        except Exception as e:
            return f"执行失败: {e}"


class PwdInput(BaseModel):
    """pwd 工具输入"""
    pass  # 无参数


class PwdTool(BaseTool):
    """获取当前工作目录"""

    name: str = "pwd"
    description: str = "获取当前工作目录的绝对路径"
    args_schema: type[BaseModel] = PwdInput

    def _run(self) -> str:
        return str(Path.cwd())


class CdInput(BaseModel):
    """cd 工具输入"""
    path: str = Field(description="目标目录")


class CdTool(BaseTool):
    """切换工作目录"""

    name: str = "cd"
    description: str = "切换当前工作目录。注意：此工具仅影响后续命令的执行目录，不会改变实际的 shell 工作目录。"
    args_schema: type[BaseModel] = CdInput

    root_dir: Path = Field(default_factory=lambda: Path.cwd())

    def _run(self, path: str) -> str:
        try:
            target = Path(path).expanduser().resolve()

            if not target.exists():
                return f"目录不存在: {path}"

            if not target.is_dir():
                return f"不是目录: {path}"

            # 注意：这里只改变工具的 root_dir，实际 shell 工作目录不变
            self.root_dir = target
            return f"已切换到: {target}"

        except Exception as e:
            return f"切换失败: {e}"
