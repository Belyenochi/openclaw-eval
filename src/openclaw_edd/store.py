"""
State 和 Artifacts 持久化

负责：
- Session K-V 状态存储（~/.openclaw_eval/state/）
- Tool 输出文件管理（~/.openclaw_eval/artifacts/）
"""

import json
from pathlib import Path
from typing import Any

# ============================================================================
# 存储路径
# ============================================================================

EVAL_HOME = Path.home() / ".openclaw_eval"
STATE_DIR = EVAL_HOME / "state"
ARTIFACTS_DIR = EVAL_HOME / "artifacts"

# 确保目录存在
STATE_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# State 管理
# ============================================================================

def state_load(session_id: str) -> dict:
    """
    加载 session 状态

    Args:
        session_id: Session ID

    Returns:
        状态 dict，不存在返回空 dict
    """
    state_file = STATE_DIR / f"{session_id}.json"
    if not state_file.exists():
        return {}
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def state_save(session_id: str, data: dict):
    """
    保存 session 状态（原子写）

    Args:
        session_id: Session ID
        data: 状态数据
    """
    state_file = STATE_DIR / f"{session_id}.json"
    tmp_file = state_file.with_suffix('.tmp')

    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    tmp_file.rename(state_file)


def state_set(session_id: str, key: str, value: Any):
    """
    设置 state 中的某个 key（支持 dotted path）

    Args:
        session_id: Session ID
        key: Key（支持 a.b.c 格式）
        value: 值
    """
    state = state_load(session_id)

    # 解析 dotted path
    parts = key.split('.')
    current = state
    for part in parts[:-1]:
        current = current.setdefault(part, {})

    # 尝试解析 JSON 值
    try:
        current[parts[-1]] = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        current[parts[-1]] = value

    state_save(session_id, state)


# ============================================================================
# Artifacts 管理
# ============================================================================

def artifacts_save(session_id: str, tool_name: str, content: str, version: int = None) -> Path:
    """
    保存 tool 输出

    Args:
        session_id: Session ID
        tool_name: Tool 名称
        content: 输出内容
        version: 版本号（None 时自动计算）

    Returns:
        保存的文件路径
    """
    session_dir = ARTIFACTS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    if version is None:
        # 自动计算版本号
        existing = list(session_dir.glob(f"{tool_name}_v*.txt"))
        version = len(existing)

    artifact_file = session_dir / f"{tool_name}_v{version}.txt"
    with open(artifact_file, 'w', encoding='utf-8') as f:
        f.write(content)

    return artifact_file


def artifacts_list(session_id: str = None) -> list[Path]:
    """
    列出 artifacts

    Args:
        session_id: Session ID（None 时列出所有）

    Returns:
        文件路径列表
    """
    if session_id:
        session_dir = ARTIFACTS_DIR / session_id
        if not session_dir.exists():
            return []
        return sorted(session_dir.glob("*.txt"))
    else:
        # 列出所有 session
        return sorted(ARTIFACTS_DIR.glob("*/*.txt"))
