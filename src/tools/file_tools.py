"""文件操作工具"""

from pathlib import Path
from typing import Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ReadInput(BaseModel):
    """read 工具输入"""
    path: str = Field(description="文件路径")
    offset: int | None = Field(default=None, description="起始行号（从1开始）")
    limit: int | None = Field(default=None, description="读取行数")


def validate_path(path: str, root_dir: Path, readonly_dirs: list[str] | None = None) -> Path:
    """验证路径安全性"""
    root_dir = root_dir.resolve()
    readonly_paths = [root_dir / d for d in (readonly_dirs or [])]

    # 解析路径
    target_path = Path(path).expanduser()

    # 如果是相对路径，相对于工作目录解析
    if not target_path.is_absolute():
        target_path = (Path.cwd() / target_path).resolve()

    target_path = target_path.resolve()

    # 检查是否在根目录内
    try:
        target_path.relative_to(root_dir)
    except ValueError:
        # 如果在工作目录外，检查是否在只读目录内
        allowed = False
        for readonly_path in readonly_paths:
            try:
                target_path.relative_to(readonly_path.resolve())
                allowed = True
                break
            except ValueError:
                continue

        if not allowed:
            raise PermissionError(f"路径不在允许范围内: {path}")

    return target_path


class ReadTool(BaseTool):
    """读取文件内容"""

    name: str = "read"
    description: str = """读取文件内容。
支持 offset 和 limit 参数进行行号范围读取。
offset: 起始行号（从1开始）
limit: 读取行数
"""
    args_schema: type[BaseModel] = ReadInput

    root_dir: Path = Field(default_factory=lambda: Path.cwd())
    readonly_dirs: list[str] = Field(default_factory=list)

    def _run(self, path: str, offset: int | None = None, limit: int | None = None) -> str:
        try:
            safe_path = validate_path(path, self.root_dir, self.readonly_dirs)

            if not safe_path.exists():
                return f"文件不存在: {safe_path}"

            content = safe_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            if offset is not None or limit is not None:
                start = max((offset or 1) - 1, 0)
                end = start + (limit or len(lines))
                selected = lines[start:end]
                return "\n".join(f"{start + i + 1:>6}|{line}" for i, line in enumerate(selected))

            return content

        except PermissionError as e:
            return f"权限错误: {e}"
        except Exception as e:
            return f"读取失败: {e}"


class WriteInput(BaseModel):
    """write 工具输入"""
    path: str = Field(description="文件路径")
    content: str = Field(description="文件内容")


class WriteTool(BaseTool):
    """写入文件"""

    name: str = "write"
    description: str = "创建新文件或覆盖已有文件的内容"
    args_schema: type[BaseModel] = WriteInput

    root_dir: Path = Field(default_factory=lambda: Path.cwd())

    def _run(self, path: str, content: str) -> str:
        try:
            safe_path = validate_path(path, self.root_dir)

            # 创建父目录
            safe_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            safe_path.write_text(content, encoding="utf-8")

            return f"已写入 {len(content)} 字符到 {safe_path}"

        except PermissionError as e:
            return f"权限错误: {e}"
        except Exception as e:
            return f"写入失败: {e}"


class EditInput(BaseModel):
    """edit 工具输入"""
    path: str = Field(description="文件路径")
    old_text: str = Field(description="要替换的旧文本")
    new_text: str = Field(description="新文本")


class EditTool(BaseTool):
    """编辑文件（精确替换）"""

    name: str = "edit"
    description: str = """在文件中进行精确的文本替换。
找到 old_text 的第一个匹配项，替换为 new_text。
"""
    args_schema: type[BaseModel] = EditInput

    root_dir: Path = Field(default_factory=lambda: Path.cwd())

    def _run(self, path: str, old_text: str, new_text: str) -> str:
        try:
            safe_path = validate_path(path, self.root_dir)

            if not safe_path.exists():
                return f"文件不存在: {safe_path}"

            content = safe_path.read_text(encoding="utf-8")

            if old_text not in content:
                return f"未找到要替换的文本"

            # 替换第一个匹配项
            new_content = content.replace(old_text, new_text, 1)

            safe_path.write_text(new_content, encoding="utf-8")

            return f"已替换 {len(old_text)} 字符为 {len(new_text)} 字符"

        except PermissionError as e:
            return f"权限错误: {e}"
        except Exception as e:
            return f"编辑失败: {e}"


class ListInput(BaseModel):
    """ls 工具输入"""
    path: str = Field(default=".", description="目录路径")
    detail: bool = Field(default=False, description="是否显示详细信息")


class ListTool(BaseTool):
    """列出目录内容"""

    name: str = "ls"
    description: str = "列出目录中的文件和子目录"
    args_schema: type[BaseModel] = ListInput

    root_dir: Path = Field(default_factory=lambda: Path.cwd())

    def _run(self, path: str = ".", detail: bool = False) -> str:
        try:
            safe_path = validate_path(path, self.root_dir)

            if not safe_path.exists():
                return f"路径不存在: {safe_path}"

            if safe_path.is_file():
                return str(safe_path)

            items = []
            for item in safe_path.iterdir():
                if detail:
                    type_str = "DIR " if item.is_dir() else "FILE"
                    items.append(f"{type_str} {item.name}")
                else:
                    items.append(item.name)

            return "\n".join(sorted(items))

        except PermissionError as e:
            return f"权限错误: {e}"
        except Exception as e:
            return f"列表失败: {e}"
