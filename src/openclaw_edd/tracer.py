"""
日志解析和事件提取

所有模块共用的核心解析逻辑，负责：
- 读取 OpenClaw 日志文件
- 解析 JSON Lines 格式
- 提取语义事件（tool_start, tool_end, llm_response）
- Session 聚合统计
- Workspace 路径解析
"""

import json
import os
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Generator, Optional

from .models import Event

# ============================================================================
# 常量
# ============================================================================

LOG_DIR = Path("/tmp/openclaw")
LOG_GLOB = "openclaw-*.log"

TOOL_START_MSGS = {"embedded run tool start", "tool_start", "run tool start"}
TOOL_END_MSGS = {"embedded run tool end", "tool_end", "run tool end"}
TURN_END_MSGS = {"run finished", "agent done", "run complete", "turn end", "response sent"}

# 正则匹配（用于快速预筛选，避免每行都 JSON 解析）
TOOL_START_RE = re.compile(
    r'"msg"\s*:\s*"(?:embedded run tool start|tool_start|run tool start)"'
    r'|"event"\s*:\s*"agent\.run\.tool_start"'
)
TOOL_END_RE = re.compile(
    r'"msg"\s*:\s*"(?:embedded run tool end|tool_end|run tool end)"'
    r'|"event"\s*:\s*"agent\.run\.tool_end"'
)

# ANSI 颜色码剥离
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


# ============================================================================
# 核心解析函数
# ============================================================================

def parse_line(line: str) -> Optional[dict]:
    """
    解析单行 JSON，自动剥离 ANSI 颜色码，支持两种日志格式

    支持的格式：
    1. 扁平格式（测试数据）：{"msg": "...", "tool": "...", "session_id": "..."}
    2. _meta 包装格式（Gateway）：{"_meta": {...}, "1": "embedded run tool start: ..."}

    Args:
        line: 日志行

    Returns:
        解析后的 dict（统一转换为扁平格式），失败或无关日志返回 None
    """
    line = ANSI_RE.sub('', line.strip())
    if not line:
        return None

    try:
        entry = json.loads(line)

        # 格式 1：扁平格式（直接返回）
        if "_meta" not in entry:
            return entry

        # 格式 2：_meta 包装格式（需要解析文本）
        # 从 "1" 字段提取信息
        msg_text = entry.get("1", "")
        if not msg_text:
            return None

        # 解析文本中的关键信息
        parsed = {}

        # 提取 sessionId
        if "sessionId=" in msg_text:
            import re
            match = re.search(r'sessionId=([a-f0-9\-]+)', msg_text)
            if match:
                parsed["session_id"] = match.group(1)

        # 提取 runId（作为备用）
        if "runId=" in msg_text and "session_id" not in parsed:
            import re
            match = re.search(r'runId=([a-f0-9\-]+)', msg_text)
            if match:
                parsed["session_id"] = match.group(1)

        # 提取 tool
        if "tool=" in msg_text:
            import re
            match = re.search(r'tool=(\w+)', msg_text)
            if match:
                parsed["tool"] = match.group(1)

        # 提取 msg 类型
        if "embedded run tool start" in msg_text:
            parsed["msg"] = "embedded run tool start"
        elif "embedded run tool end" in msg_text:
            parsed["msg"] = "embedded run tool end"
        elif "embedded run start" in msg_text:
            parsed["msg"] = "embedded run start"
        elif "embedded run done" in msg_text:
            parsed["msg"] = "embedded run done"
        elif "response sent" in msg_text:
            parsed["msg"] = "response sent"

        # 提取时间戳
        if "time" in entry:
            parsed["ts"] = entry["time"]
        elif "_meta" in entry and "date" in entry["_meta"]:
            parsed["ts"] = entry["_meta"]["date"]

        # 只返回包含 session_id 的日志
        if "session_id" in parsed:
            return parsed

        return None

    except json.JSONDecodeError:
        return None


def read_all_logs(log_dir: Path = LOG_DIR, max_file_size_mb: int = 100) -> list[dict]:
    """
    读取目录下所有 openclaw-*.log，按文件名排序

    Args:
        log_dir: 日志目录
        max_file_size_mb: 单文件大小限制（MB），超过则跳过

    Returns:
        所有日志行的 dict 列表
    """
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob(LOG_GLOB))
    entries = []
    max_bytes = max_file_size_mb * 1024 * 1024

    for log_file in log_files:
        try:
            file_size = log_file.stat().st_size
            if file_size > max_bytes:
                print(f"⚠ 跳过大文件: {log_file.name} ({file_size / 1024 / 1024:.1f}MB > {max_file_size_mb}MB)")
                print(f"  提示: 使用 --session 过滤或 trace 命令查看特定 session")
                continue

            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = parse_line(line)
                    if entry:
                        entries.append(entry)
        except Exception as e:
            print(f"⚠ 读取日志文件失败: {log_file} - {e}")

    return entries


def read_logs_for_session(log_dir: Path, session_id: str) -> list[dict]:
    """
    从日志中读取特定 session 的条目（支持大文件，使用索引）

    Args:
        log_dir: 日志目录
        session_id: Session ID 或前缀

    Returns:
        该 session 的所有日志行
    """
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob(LOG_GLOB))
    entries = []

    # 导入索引模块
    from . import indexer

    for log_file in log_files:
        try:
            # 获取索引
            idx_path = indexer.get_index_path(log_file)
            index = indexer.load_index(log_file, idx_path)

            # 查找匹配的 session
            matched_sessions = [sid for sid in index.keys() if sid.startswith(session_id)]

            if matched_sessions:
                # 使用索引快速定位
                for sid in matched_sessions:
                    offset, _ = index[sid]
                    for line in indexer.iter_session_lines(log_file, offset, sid):
                        entry = parse_line(line)
                        if entry:
                            entries.append(entry)
            else:
                # 没有索引命中，回退到全量扫描（但只扫这个文件）
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        entry = parse_line(line)
                        if entry and entry.get("session_id", "").startswith(session_id):
                            entries.append(entry)
        except Exception as e:
            print(f"⚠ 读取日志文件失败: {log_file} - {e}")

    return entries


def _is_tool_start(entry: dict) -> bool:
    """判断是否为 tool_start 事件"""
    msg = entry.get("msg", "")
    event = entry.get("event", "")
    return msg in TOOL_START_MSGS or event == "agent.run.tool_start"


def _is_tool_end(entry: dict) -> bool:
    """判断是否为 tool_end 事件"""
    msg = entry.get("msg", "")
    event = entry.get("event", "")
    return msg in TOOL_END_MSGS or event == "agent.run.tool_end"


def _is_turn_end(entry: dict) -> bool:
    """判断是否为 turn 结束事件"""
    msg = entry.get("msg", "")
    return any(end_msg in msg for end_msg in TURN_END_MSGS)


def entry_to_event(entry: dict, raw_line: str = "") -> Optional[Event]:
    """
    把一条日志 dict 转成 Event

    Args:
        entry: 日志 dict
        raw_line: 原始日志行（可选）

    Returns:
        Event 对象，不感兴趣的行返回 None
    """
    session_id = entry.get("session_id", "")
    ts = entry.get("ts", "")

    if _is_tool_start(entry):
        return Event(
            kind="tool_start",
            tool=entry.get("tool", ""),
            input=entry.get("input", {}),
            ts=ts,
            session_id=session_id,
            raw=entry
        )

    elif _is_tool_end(entry):
        return Event(
            kind="tool_end",
            tool=entry.get("tool", ""),
            output=entry.get("output", ""),
            duration_ms=entry.get("duration"),
            ts=ts,
            session_id=session_id,
            raw=entry
        )

    elif any(k in entry for k in ["response", "answer", "content"]):
        response_text = entry.get("response") or entry.get("answer") or entry.get("content", "")
        if response_text:
            return Event(
                kind="llm_response",
                output=str(response_text),
                ts=ts,
                session_id=session_id,
                raw=entry
            )

    return None


def extract_events(entries: list[dict], session_id: str = "") -> list[Event]:
    """
    从日志行列表提取语义事件序列，自动配对 tool start/end

    Args:
        entries: 日志行列表
        session_id: 可选的 session 过滤（前缀匹配）

    Returns:
        Event 列表
    """
    events = []
    pending = {}  # tool_name -> start_entry

    for entry in entries:
        sid = entry.get("session_id", "")

        # 过滤 session
        if session_id and not sid.startswith(session_id):
            continue

        if _is_tool_start(entry):
            tool = entry.get("tool", "")
            events.append(Event(
                kind="tool_start",
                tool=tool,
                input=entry.get("input", {}),
                ts=entry.get("ts", ""),
                session_id=sid,
                raw=entry
            ))
            pending[tool] = entry

        elif _is_tool_end(entry):
            tool = entry.get("tool", "")
            start_entry = pending.pop(tool, {})
            events.append(Event(
                kind="tool_end",
                tool=tool,
                input=start_entry.get("input", {}),
                output=entry.get("output", ""),
                duration_ms=entry.get("duration"),
                ts=entry.get("ts", ""),
                session_id=sid,
                raw=entry
            ))

        elif any(k in entry for k in ["response", "answer", "content"]):
            response_text = entry.get("response") or entry.get("answer") or entry.get("content", "")
            if response_text:
                events.append(Event(
                    kind="llm_response",
                    output=str(response_text),
                    ts=entry.get("ts", ""),
                    session_id=sid,
                    raw=entry
                ))

    return events


def sessions_from_logs(log_dir: Path = LOG_DIR) -> list[dict]:
    """
    扫描全量日志，按 session_id 聚合统计（使用索引优化）

    Args:
        log_dir: 日志目录

    Returns:
        Session 统计列表，按 last_ts 倒序
        每个 dict 包含：session_id, first_ts, last_ts, tool_count, turns, agent
    """
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob(LOG_GLOB))
    sessions = defaultdict(lambda: {
        "session_id": "",
        "first_ts": "",
        "last_ts": "",
        "tool_count": 0,
        "turns": 0,
        "agent": "",
    })

    # 导入索引模块
    from . import indexer

    for log_file in log_files:
        try:
            file_size = log_file.stat().st_size

            # 所有文件都使用索引（优化性能）
            # 构建/加载索引
            idx_path = indexer.get_index_path(log_file)
            index = indexer.load_index(log_file, idx_path)

            # 对每个 session 读取其日志行
            for session_id in index.keys():
                offset, _ = index[session_id]
                for line in indexer.iter_session_lines(log_file, offset, session_id):
                    entry = parse_line(line)
                    if not entry:
                        continue

                    session = sessions[session_id]
                    session["session_id"] = session_id

                    ts = entry.get("ts", "")
                    if not session["first_ts"] or ts < session["first_ts"]:
                        session["first_ts"] = ts
                    if not session["last_ts"] or ts > session["last_ts"]:
                        session["last_ts"] = ts

                    if _is_tool_end(entry):
                        session["tool_count"] += 1

                    if _is_turn_end(entry):
                        session["turns"] += 1

                    if not session["agent"] and "agent" in entry:
                        session["agent"] = entry["agent"]

        except Exception as e:
            print(f"⚠ 处理日志文件失败: {log_file} - {e}")

    # 按 last_ts 倒序
    result = sorted(sessions.values(), key=lambda x: x["last_ts"], reverse=True)
    return result


def tail_f(path: Path, from_end: bool = True) -> Generator[str, None, None]:
    """
    流式读取文件新增行的生成器

    Args:
        path: 文件路径
        from_end: 是否从文件末尾开始（True 时只读新增内容）

    Yields:
        新增的行
    """
    if not path.exists():
        # 等待文件创建
        while not path.exists():
            time.sleep(0.5)

    current_inode = os.stat(path).st_ino
    current_date = date.today()

    with open(path, 'r', encoding='utf-8') as f:
        if from_end:
            f.seek(0, 2)  # 跳到文件末尾

        while True:
            line = f.readline()
            if line:
                yield line
            else:
                # 检查日志轮转
                time.sleep(0.05)

                # 检查跨天
                new_date = date.today()
                if new_date != current_date:
                    # 切换到新日志文件
                    new_path = path.parent / f"openclaw-{new_date.strftime('%Y-%m-%d')}.log"
                    if new_path.exists():
                        path = new_path
                        current_date = new_date
                        current_inode = os.stat(path).st_ino
                        f.close()
                        f = open(path, 'r', encoding='utf-8')
                        continue

                # 检查 inode 变化
                try:
                    new_inode = os.stat(path).st_ino
                    if new_inode != current_inode:
                        # 文件被轮转，重新打开
                        current_inode = new_inode
                        f.close()
                        f = open(path, 'r', encoding='utf-8')
                except FileNotFoundError:
                    # 文件被删除，等待重新创建
                    time.sleep(0.5)
                    if path.exists():
                        current_inode = os.stat(path).st_ino
                        f.close()
                        f = open(path, 'r', encoding='utf-8')


def get_workspace(override: str = "") -> Path:
    """
    Workspace 路径解析

    优先级：
    1. override 参数（非空时直接用）
    2. ~/.openclaw/openclaw.json → agents.defaults.workspace
    3. fallback: ~/.openclaw/workspace

    Args:
        override: 覆盖路径

    Returns:
        Workspace 路径
    """
    if override:
        return Path(override).expanduser()

    # 尝试从配置文件读取
    config_file = Path.home() / ".openclaw" / "openclaw.json"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                workspace = config.get("agents", {}).get("defaults", {}).get("workspace")
                if workspace:
                    return Path(workspace).expanduser()
        except Exception:
            pass

    # Fallback
    return Path.home() / ".openclaw" / "workspace"
