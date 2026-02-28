"""
CLI 入口

注册所有子命令，提供统一的命令行接口
"""

import argparse
import sys

from . import watcher, eval as eval_module, edd


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        prog="edd",
        description="OpenClaw EDD toolkit - Evaluation-Driven Development"
    )
    
    # 全局选项
    parser.add_argument("--verbose", "-v", action="store_true", help="打印调试信息")
    parser.add_argument("--log-dir", default="/tmp/openclaw", help="日志目录")
    
    subparsers = parser.add_subparsers(dest="cmd", required=True, help="子命令")
    
    # ========================================================================
    # watch 命令
    # ========================================================================
    watch_parser = subparsers.add_parser("watch", help="实时监听日志")
    watch_parser.add_argument("--session", help="过滤特定 session")
    watch_parser.add_argument("--from-start", action="store_true", help="从文件头读")
    watch_parser.add_argument("--daemon", action="store_true", help="后台运行")
    watch_parser.add_argument("--pid-file", default="/tmp/openclaw_edd_watch.pid", help="PID 文件")
    watch_parser.add_argument("--daemon-log", default="/tmp/openclaw_edd_watch.log", help="Daemon 日志")
    
    # ========================================================================
    # trace 命令
    # ========================================================================
    trace_parser = subparsers.add_parser("trace", help="回放历史事件链")
    trace_parser.add_argument("--session", required=True, help="Session ID")
    trace_parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    
    # ========================================================================
    # state 命令
    # ========================================================================
    state_parser = subparsers.add_parser("state", help="查看/修改 session 状态")
    state_parser.add_argument("--session", required=True, help="Session ID")
    state_parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    state_parser.add_argument("--set", action="append", help="设置 key=value")
    state_parser.add_argument("--delete", action="append", help="删除 key")
    
    # ========================================================================
    # artifacts 命令
    # ========================================================================
    artifacts_parser = subparsers.add_parser("artifacts", help="管理 tool 输出文件")
    artifacts_parser.add_argument("--session", help="Session ID")
    artifacts_parser.add_argument("--extract", action="store_true", help="从日志提取")
    artifacts_parser.add_argument("--export", help="导出到指定目录")
    
    # ========================================================================
    # sessions 命令
    # ========================================================================
    sessions_parser = subparsers.add_parser("sessions", help="列出/查看历史 session")
    sessions_parser.add_argument("--limit", type=int, default=20, help="显示数量限制")
    sessions_parser.add_argument("--show", help="显示单个 session 详情")
    
    # ========================================================================
    # run 命令
    # ========================================================================
    run_parser = subparsers.add_parser("run", help="运行 eval 用例集")
    run_parser.add_argument("--cases", help="用例文件（YAML）")
    run_parser.add_argument("--tags", nargs="+", help="过滤 tags")
    run_parser.add_argument("--case", help="单个用例消息")
    run_parser.add_argument("--expect-tools", nargs="+", help="期望工具列表")
    run_parser.add_argument("--forbidden-tools", nargs="+", help="禁止工具列表")
    run_parser.add_argument("--agent", default="main", help="Agent 名称")
    run_parser.add_argument("--local", action="store_true", help="使用 --local 模式运行（日志会写入本地）")
    run_parser.add_argument("--dry-run", action="store_true", help="不发消息，只解析日志")
    run_parser.add_argument("--session", help="Dry-run 模式下指定 session_id")
    run_parser.add_argument("--show-trace", action="store_true", help="显示详细的工具调用 trace")
    run_parser.add_argument("--baseline", help="基线报告文件（JSON），用于对比")
    run_parser.add_argument("--output-json", help="保存 JSON 报告")
    run_parser.add_argument("--output-html", help="保存 HTML 报告")
    
    # ========================================================================
    # gen-cases 命令
    # ========================================================================
    gen_cases_parser = subparsers.add_parser("gen-cases", help="生成用例模板")
    gen_cases_parser.add_argument("--output", help="输出文件")
    gen_cases_parser.add_argument("--force", action="store_true", help="覆盖已存在的文件")

    # ========================================================================
    # edd 命令（包含子子命令）
    # ========================================================================
    edd_parser = subparsers.add_parser("edd", help="EDD 闭环命令")
    edd_subparsers = edd_parser.add_subparsers(dest="edd_cmd", required=True, help="EDD 子命令")

    # edd suggest
    suggest_parser = edd_subparsers.add_parser("suggest", help="从失败 cases 生成修改建议")
    suggest_parser.add_argument("--report", required=True, help="JSON 报告文件")
    suggest_parser.add_argument("--workspace", default="", help="Workspace 路径")

    # edd apply
    apply_parser = edd_subparsers.add_parser("apply", help="应用建议到 workspace")
    apply_parser.add_argument("--suggestion-file", required=True, help="建议文件")
    apply_parser.add_argument("--yes", action="store_true", help="跳过确认")
    apply_parser.add_argument("--workspace", default="", help="Workspace 路径")

    # edd diff
    diff_parser = edd_subparsers.add_parser("diff", help="对比两次 run 的变化")
    diff_parser.add_argument("--before", required=True, help="之前的报告")
    diff_parser.add_argument("--after", required=True, help="之后的报告")
    diff_parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")

    # edd mine
    mine_parser = edd_subparsers.add_parser("mine", help="从历史日志挖掘 golden cases")
    mine_parser.add_argument("--output", default="mined_cases.yaml", help="输出文件")
    mine_parser.add_argument("--min-tools", type=int, default=1, help="最少工具调用数")
    mine_parser.add_argument("--log-dir", help="日志目录")
    mine_parser.add_argument("--workspace", default="", help="Workspace 路径")

    # edd judge
    judge_parser = edd_subparsers.add_parser("judge", help="用 LLM 对 tool 选择和 output 质量打分")
    judge_parser.add_argument("--report", required=True, help="JSON 报告文件")
    judge_parser.add_argument("--output", help="输出打分报告（JSON）")
    judge_parser.add_argument("--model", default="claude-sonnet-4-6", help="LLM 模型（支持 claude-opus-4-6, claude-sonnet-4-6, claude-haiku-4-5, gpt-4o, deepseek-chat 等）")
    judge_parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai", "deepseek"], help="LLM 提供商")
    
    # edd export
    export_parser = edd_subparsers.add_parser("export", help="导出 golden dataset")
    export_parser.add_argument("--output", default="golden.jsonl", help="输出文件")
    export_parser.add_argument("--min-tools", type=int, default=1, help="最少工具调用数")
    export_parser.add_argument("--log-dir", help="日志目录")
    export_parser.add_argument("--workspace", default="", help="Workspace 路径")
    export_parser.add_argument("--merge-report", help="合并 report 的 final_output")
    export_parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl", help="输出格式")
    
    # 解析参数
    args = parser.parse_args()
    
    # 分发到对应命令
    try:
        if args.cmd == "watch":
            watcher.cmd_watch(args)
        elif args.cmd == "trace":
            cmd_trace(args)
        elif args.cmd == "state":
            cmd_state(args)
        elif args.cmd == "artifacts":
            cmd_artifacts(args)
        elif args.cmd == "sessions":
            cmd_sessions(args)
        elif args.cmd == "run":
            eval_module.cmd_run(args)
        elif args.cmd == "gen-cases":
            eval_module.cmd_gen_cases(args)
        elif args.cmd == "edd":
            edd.cmd_edd(args)
    except KeyboardInterrupt:
        print("\n\n✗ 用户中断")
        sys.exit(130)
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        else:
            print(f"✗ 错误: {e}")
        sys.exit(1)


# ============================================================================
# 简化的命令实现（trace, state, artifacts, sessions）
# ============================================================================

def cmd_trace(args):
    """Trace 命令"""
    from .tracer import read_logs_for_session, extract_events, LOG_DIR
    from pathlib import Path
    import json
    
    log_dir = Path(args.log_dir)
    entries = read_logs_for_session(log_dir, args.session)
    events = extract_events(entries, args.session)
    
    if not events:
        print(f"✗ 未找到 session: {args.session}")
        sys.exit(1)
    
    if args.format == "json":
        output = [e.to_dict() for e in events]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return
    
    print(f"📋 Trace  session={args.session}  ({len(events)} events)")
    print("─" * 60)
    
    for i, event in enumerate(events, 1):
        if event.kind == "tool_start":
            print(f"#{i:02d} TOOL_START  {event.tool}  {event.ts}")
            if event.input:
                print(f"     input: {json.dumps(event.input, ensure_ascii=False)}")
        
        elif event.kind == "tool_end":
            duration_str = f"{event.duration_ms}ms" if event.duration_ms else ""
            print(f"#{i:02d} TOOL_END    {event.tool}  {duration_str}  {event.ts}")
            if event.output:
                output_str = event.output[:100] + "..." if len(event.output) > 100 else event.output
                print(f"     output: {output_str}")
        
        elif event.kind == "llm_response":
            print(f"#{i:02d} LLM_RESP    {event.ts}")
            output_str = event.output[:200] + "..." if len(event.output) > 200 else event.output
            print(f"     {output_str}")


def cmd_state(args):
    """State 命令"""
    from . import store
    from .tracer import read_logs_for_session, extract_events, LOG_DIR
    from pathlib import Path
    import json
    
    state = store.state_load(args.session)
    
    # 如果不存在，从日志初始化
    if not state:
        log_dir = Path(args.log_dir)
        entries = read_logs_for_session(log_dir, args.session)
        events = extract_events(entries, args.session)
        if events:
            state = {
                "tool_history": [
                    {"tool": e.tool, "ts": e.ts, "input": e.input}
                    for e in events if e.kind == "tool_end"
                ]
            }
    
    # 修改操作
    if args.set:
        for kv in args.set:
            if '=' not in kv:
                print(f"✗ 无效格式: {kv}")
                continue
            key, value = kv.split('=', 1)
            store.state_set(args.session, key, value)
        print("✓ State 已更新")
    
    if args.delete:
        for key in args.delete:
            state.pop(key, None)
        store.state_save(args.session, state)
        print("✓ State 已更新")
    
    # 显示
    if args.format == "json":
        print(json.dumps(state, indent=2, ensure_ascii=False))
    else:
        print(f"🗂  State  session={args.session}")
        print("─" * 60)
        if state:
            print(json.dumps(state, indent=2, ensure_ascii=False))
        else:
            print("  (空)")


def cmd_artifacts(args):
    """Artifacts 命令"""
    from . import store
    from .tracer import read_logs_for_session, extract_events, LOG_DIR
    from pathlib import Path
    import shutil
    from collections import defaultdict
    
    if args.extract:
        if not args.session:
            print("✗ --extract 需要指定 --session")
            sys.exit(1)
        
        log_dir = Path(args.log_dir)
        entries = read_logs_for_session(log_dir, args.session)
        events = extract_events(entries, args.session)
        
        count = 0
        for event in events:
            if event.kind == "tool_end" and event.output:
                store.artifacts_save(event.session_id, event.tool, str(event.output))
                count += 1
        
        print(f"✓ 已提取 {count} 个 artifacts")
        return
    
    if args.export:
        export_dir = Path(args.export)
        export_dir.mkdir(parents=True, exist_ok=True)
        
        files = store.artifacts_list(args.session) if args.session else store.artifacts_list()
        
        for src in files:
            rel_path = src.relative_to(store.ARTIFACTS_DIR)
            dst = export_dir / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        
        print(f"✓ 已导出 {len(files)} 个文件到 {export_dir}")
        return
    
    # 列出
    if args.session:
        files = store.artifacts_list(args.session)
        if not files:
            print(f"✗ 未找到 artifacts: {args.session}")
            return
        
        print(f"📦 Artifacts  session={args.session}")
        print("─" * 60)
        for f in files:
            size = f.stat().st_size
            print(f"  {f.name}  {size:>8}B")
    else:
        sessions = defaultdict(list)
        for f in store.artifacts_list():
            session_id = f.parent.name
            sessions[session_id].append(f)
        
        if not sessions:
            print("✗ 未找到任何 artifacts")
            return
        
        print("📦 Artifacts")
        print("─" * 60)
        for session_id in sorted(sessions.keys()):
            files = sessions[session_id]
            print(f"  {session_id}  ({len(files)} files)")
            for f in files:
                size = f.stat().st_size
                print(f"    {f.name}  {size:>8}B")


def cmd_sessions(args):
    """Sessions 命令"""
    from .tracer import sessions_from_logs, read_logs_for_session, extract_events, LOG_DIR
    from . import store
    from pathlib import Path
    
    log_dir = Path(args.log_dir)
    
    if args.show:
        entries = read_logs_for_session(log_dir, args.show)
        events = extract_events(entries, args.show)
        
        if not events:
            print(f"✗ 未找到 session: {args.show}")
            sys.exit(1)
        
        state = store.state_load(args.show)
        artifacts = store.artifacts_list(args.show)
        
        print(f"🗂  Session  {args.show}")
        print("─" * 60)
        print(f"Events: {len(events)}")
        print(f"State keys: {len(state)}")
        print(f"Artifacts: {len(artifacts)}")
        print()
        
        tool_calls = [e.tool for e in events if e.kind == "tool_end"]
        if tool_calls:
            print("Tool calls:")
            for tool in tool_calls:
                print(f"  - {tool}")
        
        return
    
    # 列出所有
    sessions = sessions_from_logs(log_dir)
    
    if not sessions:
        print("✗ 未找到任何 session")
        return
    
    # 检查 state/artifacts
    has_state = set()
    has_artifacts = set()
    for s in sessions:
        sid = s["session_id"]
        if (store.STATE_DIR / f"{sid}.json").exists():
            has_state.add(sid)
        if store.artifacts_list(sid):
            has_artifacts.add(sid)
    
    display_sessions = sessions[:args.limit]
    
    print(f"🗂  Sessions  ({len(sessions)} total)")
    print("─" * 80)
    print(f"  {'SESSION_ID':<40}  {'TOOLS':>5}  {'TURNS':>5}  {'LAST_SEEN':<20}")
    print("  " + "─" * 76)
    
    for s in display_sessions:
        sid = s["session_id"]
        tools = s["tool_count"]
        turns = s["turns"]
        last_ts = s["last_ts"][:16] if s["last_ts"] else ""
        
        flags = ""
        if sid in has_state:
            flags += "[S]"
        if sid in has_artifacts:
            flags += "[A]"
        
        print(f"  {sid:<40}  {tools:>5}  {turns:>5}  {last_ts:<20}  {flags}")
    
    if len(sessions) > args.limit:
        print(f"\n  ... {len(sessions) - args.limit} more (use --limit to show more)")
    
    print("\n  [S]=有State  [A]=有Artifacts")


if __name__ == "__main__":
    main()
