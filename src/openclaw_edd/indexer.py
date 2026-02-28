"""
Session 索引管理

为大日志文件建立轻量级 session byte-offset 索引，避免全量读取
"""

import json
import os
import sys
from pathlib import Path
from typing import Generator

from .store import EVAL_HOME

# 索引目录
INDEX_DIR = EVAL_HOME / "index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)


def build_index(log_path: Path, idx_path: Path) -> dict[str, tuple[int, int]]:
    """
    全量扫描日志文件，构建 session_id → (byte_offset, line_count) 映射

    Args:
        log_path: 日志文件路径
        idx_path: 索引文件路径

    Returns:
        session_id → (byte_offset, line_count) 的映射
    """
    if not log_path.exists():
        return {}

    file_size = log_path.stat().st_size
    session_map = {}  # session_id → (first_offset, line_count)
    session_lines = {}  # session_id → line_count

    print(f"扫描中: {log_path.name} 0% (0MB / {file_size // 1024 // 1024}MB)", file=sys.stderr, end='\r')

    with open(log_path, 'r', encoding='utf-8') as f:
        offset = 0
        last_progress = 0

        while True:
            line = f.readline()
            if not line:
                break

            line_len = len(line.encode('utf-8'))

            # 解析 session_id（使用 parse_line 支持两种格式）
            try:
                from .tracer import parse_line
                parsed = parse_line(line)
                if parsed and "session_id" in parsed:
                    session_id = parsed["session_id"]
                    if session_id:
                        if session_id not in session_map:
                            session_map[session_id] = (offset, 0)
                        session_lines[session_id] = session_lines.get(session_id, 0) + 1
            except:
                pass

            offset += line_len

            # 打印进度（每 500MB）
            if offset - last_progress >= 500 * 1024 * 1024:
                progress = int(offset / file_size * 100)
                print(f"扫描中: {log_path.name} {progress}% ({offset // 1024 // 1024}MB / {file_size // 1024 // 1024}MB)", file=sys.stderr, end='\r')
                last_progress = offset

    print(f"扫描完成: {log_path.name} 100% ({file_size // 1024 // 1024}MB / {file_size // 1024 // 1024}MB)", file=sys.stderr)

    # 更新 line_count
    result = {}
    for session_id, (first_offset, _) in session_map.items():
        line_count = session_lines.get(session_id, 0)
        result[session_id] = (first_offset, line_count)

    # 写入索引文件
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    with open(idx_path, 'w', encoding='utf-8') as f:
        for session_id, (byte_offset, line_count) in sorted(result.items()):
            f.write(f"{session_id}\t{byte_offset}\t{line_count}\n")

    return result


def load_index(log_path: Path, idx_path: Path) -> dict[str, tuple[int, int]]:
    """
    加载或构建索引

    如果索引存在且是最新的，直接读取；否则重建或增量更新

    Args:
        log_path: 日志文件路径
        idx_path: 索引文件路径

    Returns:
        session_id → (byte_offset, line_count) 的映射
    """
    if not log_path.exists():
        return {}

    log_mtime = log_path.stat().st_mtime
    log_size = log_path.stat().st_size

    # 检查索引是否存在且最新
    if idx_path.exists():
        idx_mtime = idx_path.stat().st_mtime

        if idx_mtime >= log_mtime:
            # 索引是最新的，直接读取
            result = {}
            with open(idx_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) == 3:
                        session_id, byte_offset, line_count = parts
                        result[session_id] = (int(byte_offset), int(line_count))
            return result

        # 索引过期，尝试增量更新
        # 读取现有索引
        existing = {}
        last_offset = 0
        with open(idx_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) == 3:
                    session_id, byte_offset, line_count = parts
                    offset = int(byte_offset)
                    existing[session_id] = (offset, int(line_count))
                    last_offset = max(last_offset, offset)

        # 从上次结束位置继续扫描
        print(f"增量扫描: {log_path.name} 从 {last_offset // 1024 // 1024}MB 开始", file=sys.stderr)

        session_lines = {sid: lc for sid, (_, lc) in existing.items()}

        with open(log_path, 'r', encoding='utf-8') as f:
            f.seek(last_offset)
            offset = last_offset

            while True:
                line = f.readline()
                if not line:
                    break

                line_len = len(line.encode('utf-8'))

                # 解析 session_id（使用 parse_line 支持两种格式）
                try:
                    from .tracer import parse_line
                    parsed = parse_line(line)
                    if parsed and "session_id" in parsed:
                        session_id = parsed["session_id"]
                        if session_id:
                            if session_id not in existing:
                                existing[session_id] = (offset, 0)
                            session_lines[session_id] = session_lines.get(session_id, 0) + 1
                except:
                    pass

                offset += line_len

        # 更新 line_count
        result = {}
        for session_id, (first_offset, _) in existing.items():
            line_count = session_lines.get(session_id, 0)
            result[session_id] = (first_offset, line_count)

        # 重写索引文件
        with open(idx_path, 'w', encoding='utf-8') as f:
            for session_id, (byte_offset, line_count) in sorted(result.items()):
                f.write(f"{session_id}\t{byte_offset}\t{line_count}\n")

        print(f"增量扫描完成: {log_path.name}", file=sys.stderr)
        return result

    # 索引不存在，全量构建
    return build_index(log_path, idx_path)


def iter_session_lines(log_path: Path, offset: int, target_session_id: str) -> Generator[str, None, None]:
    """
    从指定 offset 开始，逐行 yield 该 session 的所有行

    Args:
        log_path: 日志文件路径
        offset: 起始字节偏移
        target_session_id: 目标 session ID

    Yields:
        该 session 的日志行
    """
    if not log_path.exists():
        return

    with open(log_path, 'r', encoding='utf-8') as f:
        f.seek(offset)

        while True:
            line = f.readline()
            if not line:
                break

            # 检查是否属于目标 session（使用 parse_line 支持两种格式）
            try:
                from .tracer import parse_line
                parsed = parse_line(line)
                
                if parsed and "session_id" in parsed:
                    session_id = parsed["session_id"]

                    if session_id == target_session_id:
                        yield line
                    elif session_id and session_id != target_session_id:
                        # 遇到不同 session，停止
                        break
                else:
                    # 没有 session_id 的行，继续
                    continue
            except:
                # 解析失败，继续
                continue


def get_index_path(log_path: Path) -> Path:
    """获取日志文件对应的索引文件路径"""
    return INDEX_DIR / f"{log_path.name}.idx"
