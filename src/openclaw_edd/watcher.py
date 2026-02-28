"""
Watch 命令实现

实时监听日志文件，打印 tool 事件流，自动写入 State 和 Artifacts
"""

import json
import os
import signal
import sys
from datetime import date
from pathlib import Path

from . import tracer, store


def cmd_watch(args):
    """Watch 命令入口"""
    log_path = Path(args.log_dir) / f"openclaw-{date.today().strftime('%Y-%m-%d')}.log"

    if args.daemon:
        # Daemon 模式
        if sys.platform == "win32":
            print("✗ Daemon 模式仅支持 Linux/macOS")
            sys.exit(1)

        pid = os.fork()
        if pid > 0:
            # 父进程：写 PID 文件并退出
            with open(args.pid_file, 'w') as f:
                f.write(str(pid))
            print(f"✓ Watch daemon 已启动 (PID: {pid})")
            print(f"  日志: {args.daemon_log}")
            print(f"  停止: kill $(cat {args.pid_file})")
            sys.exit(0)

        # 子进程：脱离终端
        os.setsid()
        sys.stdout = open(args.daemon_log, 'a', encoding='utf-8')
        sys.stderr = sys.stdout

    # 信号处理
    running = [True]

    def signal_handler(signum, frame):
        running[0] = False

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print(f"👁  监听日志: {log_path}")
    if args.session:
        print(f"   过滤 session: {args.session}")

    try:
        for line in tracer.tail_f(log_path, from_end=not args.from_start):
            if not running[0]:
                break

            entry = tracer.parse_line(line)
            if not entry:
                continue

            session_id = entry.get("session_id", "")
            if args.session and not session_id.startswith(args.session):
                continue

            # 打印事件
            if tracer._is_tool_start(entry):
                tool = entry.get("tool", "")
                ts = entry.get("ts", "")
                input_data = entry.get("input", {})

                print(f"▶ {tool}  [{session_id[:8]}]  {ts}")
                if input_data:
                    input_str = json.dumps(input_data, ensure_ascii=False)
                    if len(input_str) > 100:
                        input_str = input_str[:97] + "..."
                    print(f"  in: {input_str}")

                # 自动写入 State
                state = store.state_load(session_id)
                state.setdefault("tool_history", []).append({
                    "tool": tool,
                    "ts": ts,
                    "input": input_data
                })
                store.state_save(session_id, state)

            elif tracer._is_tool_end(entry):
                tool = entry.get("tool", "")
                duration = entry.get("duration", 0)
                output = entry.get("output", "")

                print(f"✓ {tool}  {duration}ms  [{session_id[:8]}]")
                if output:
                    output_str = str(output)
                    if len(output_str) > 100:
                        output_str = output_str[:97] + "..."
                    print(f"  out: {output_str}")

                # 自动保存 Artifact
                artifact_path = store.artifacts_save(session_id, tool, str(output))
                print(f"  artifact: {artifact_path}")

            elif any(k in entry for k in ["response", "answer", "content"]):
                response = entry.get("response") or entry.get("answer") or entry.get("content", "")
                if response:
                    response_str = str(response)
                    if len(response_str) > 200:
                        response_str = response_str[:197] + "..."
                    print(f"◎ llm  [{session_id[:8]}]")
                    print(f"  {response_str}")

                    # 更新 State
                    state = store.state_load(session_id)
                    state["last_response"] = response_str
                    store.state_save(session_id, state)

    except KeyboardInterrupt:
        pass

    print("\n✓ Watch 已停止")
