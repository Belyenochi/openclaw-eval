"""
EDD 闭环命令

负责：
- suggest: 从失败 cases 生成修改建议
- apply: 应用建议到 workspace
- diff: 对比两次 run 的变化
- mine: 从历史日志挖掘 golden cases
- export: 导出 golden dataset（JSONL 格式）
"""

import csv
import difflib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .tracer import read_all_logs, extract_events, get_workspace, _is_turn_end, sessions_from_logs


# ============================================================================
# suggest 命令
# ============================================================================

def analyze_failure(result: dict, workspace: Path) -> dict:
    """分析失败原因，生成建议"""
    case_id = result["case"]["id"]
    message = result["case"]["message"]
    failures = result.get("failures", [])
    tool_names = result.get("tool_names", [])

    suggestion = {
        "case_id": case_id,
        "message": message,
        "failures": failures,
        "recommendations": []
    }

    for failure in failures:
        if "缺少必要工具调用" in failure:
            # 提取缺失的工具
            import re
            match = re.search(r"'(\w+)'", failure)
            if match:
                missing_tool = match.group(1)

                # 检查是否有对应 skill
                skills_dir = workspace / "skills"
                skill_file = skills_dir / f"{missing_tool}.md"

                if skill_file.exists():
                    suggestion["recommendations"].append({
                        "type": "modify_skill",
                        "file": f"skills/{missing_tool}.md",
                        "action": f"补充工具调用步骤：{missing_tool}"
                    })
                else:
                    suggestion["recommendations"].append({
                        "type": "create_skill",
                        "file": f"skills/{case_id}.md",
                        "action": f"新建 skill，包含工具调用：{missing_tool}"
                    })

        elif "工具调用顺序不符" in failure:
            suggestion["recommendations"].append({
                "type": "modify_skill",
                "file": f"skills/{case_id}.md",
                "action": "调整工具调用顺序"
            })

        elif "调用了禁止的工具" in failure:
            suggestion["recommendations"].append({
                "type": "modify_tools",
                "file": "TOOLS.md",
                "action": "在使用约定中添加禁止规则"
            })

        elif "输出缺少关键词" in failure:
            suggestion["recommendations"].append({
                "type": "modify_skill",
                "file": f"skills/{case_id}.md",
                "action": "补充输出格式要求"
            })

        elif "工具参数不符" in failure:
            # 提取工具名和参数信息
            import re
            match = re.search(r"工具参数不符: (\w+)\.(\w+) 期望=(\S+) 实际=(\S+)", failure)
            if match:
                tool_name, arg_key, expected, actual = match.groups()
                suggestion["recommendations"].append({
                    "type": "modify_skill",
                    "file": f"skills/{case_id}.md",
                    "action": f"在 skill 文件里明确工具调用参数：{tool_name} 应使用 {arg_key}={expected}"
                })

    return suggestion


def cmd_suggest(args):
    """Suggest 命令入口"""
    if not Path(args.report).exists():
        print(f"✗ 报告文件不存在: {args.report}")
        sys.exit(1)

    with open(args.report, 'r', encoding='utf-8') as f:
        results = json.load(f)

    workspace = get_workspace(args.workspace)
    failed_results = [r for r in results if not r.get("passed", False)]

    if not failed_results:
        print("✓ 所有用例通过，无需建议")
        return

    print(f"📋 分析 {len(failed_results)} 个失败用例\n")

    for result in failed_results:
        suggestion = analyze_failure(result, workspace)
        
        print(f"=== case: {suggestion['case_id']} ===")
        print(f"消息: {suggestion['message']}")
        for failure in suggestion['failures']:
            print(f"失败原因: {failure}")
        
        for rec in suggestion['recommendations']:
            print(f"建议文件: {rec['file']}")
            print(f"建议内容: {rec['action']}")
        
        print("─" * 60)
        print()


# ============================================================================
# apply 命令
# ============================================================================

READONLY_FILES = {"SOUL.md", "AGENTS.md", "USER.md", "BOOTSTRAP.md", "IDENTITY.md"}


def apply_suggestion(suggestion: dict, workspace: Path, auto_yes: bool = False):
    """应用单个建议"""
    for rec in suggestion['recommendations']:
        file_path = workspace / rec['file']
        
        # 检查只读文件
        if file_path.name in READONLY_FILES:
            print(f"[SKIP] {file_path.name} 为只读文件，请手动修改")
            print(f"建议内容: {rec['action']}")
            continue

        # 生成修改内容
        if rec['type'] == 'create_skill':
            content = f"""# {suggestion['case_id']}

## 触发条件
{suggestion['message']}

## 步骤
1. {rec['action']}

## 输出格式
包含相关信息的自然语言回复
"""
            if file_path.exists():
                print(f"[SKIP] {file_path} 已存在")
                continue

            # 显示 diff
            print(f"\n[CREATE] {file_path}")
            print(content)

            if not auto_yes:
                confirm = input("确认创建? (y/n): ")
                if confirm.lower() != 'y':
                    print("[SKIP]")
                    continue

            # 原子写
            file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = file_path.with_suffix('.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            tmp_file.rename(file_path)
            print(f"✓ 已创建: {file_path}")

        elif rec['type'] == 'modify_tools':
            if not file_path.exists():
                print(f"[SKIP] {file_path} 不存在")
                continue

            with open(file_path, 'r', encoding='utf-8') as f:
                original = f.read()

            # 查找"## 使用约定" section
            if "## 使用约定" in original:
                new_content = original + f"\n- {rec['action']}\n"
            else:
                new_content = original + f"\n\n## 使用约定\n- {rec['action']}\n"

            # 显示 diff
            print(f"\n[MODIFY] {file_path}")
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(file_path),
                tofile=str(file_path)
            )
            print(''.join(diff))

            if not auto_yes:
                confirm = input("确认修改? (y/n): ")
                if confirm.lower() != 'y':
                    print("[SKIP]")
                    continue

            # 原子写
            tmp_file = file_path.with_suffix('.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            tmp_file.rename(file_path)
            print(f"✓ 已修改: {file_path}")


def cmd_apply(args):
    """Apply 命令入口"""
    if not Path(args.suggestion_file).exists():
        print(f"✗ 建议文件不存在: {args.suggestion_file}")
        sys.exit(1)

    # 解析建议文件（简化版，实际应该解析 suggest 的输出）
    print("⚠ apply 命令需要配合 suggest 输出使用")
    print("当前版本为简化实现")


# ============================================================================
# diff 命令
# ============================================================================

def cmd_diff(args):
    """Diff 命令入口"""
    if not Path(args.before).exists() or not Path(args.after).exists():
        print("✗ 报告文件不存在")
        sys.exit(1)

    with open(args.before, 'r', encoding='utf-8') as f:
        before_results = json.load(f)
    with open(args.after, 'r', encoding='utf-8') as f:
        after_results = json.load(f)

    # 计算整体指标
    before_passed = sum(1 for r in before_results if r.get("passed", False))
    after_passed = sum(1 for r in after_results if r.get("passed", False))
    before_rate = before_passed / len(before_results) * 100 if before_results else 0
    after_rate = after_passed / len(after_results) * 100 if after_results else 0

    before_avg = sum(r.get("duration_s", 0) for r in before_results) / len(before_results) if before_results else 0
    after_avg = sum(r.get("duration_s", 0) for r in after_results) / len(after_results) if after_results else 0

    print("📊 EDD Diff")
    print(f"baseline : {args.before}")
    print(f"new      : {args.after}")
    print("─" * 60)

    # 按 eval_type 分组统计
    before_regression = [r for r in before_results if r.get("case", {}).get("eval_type", "regression") == "regression"]
    after_regression = [r for r in after_results if r.get("case", {}).get("eval_type", "regression") == "regression"]
    before_capability = [r for r in before_results if r.get("case", {}).get("eval_type", "regression") == "capability"]
    after_capability = [r for r in after_results if r.get("case", {}).get("eval_type", "regression") == "capability"]

    if before_regression or after_regression:
        before_reg_rate = (sum(1 for r in before_regression if r.get("passed", False)) / len(before_regression) * 100) if before_regression else 0
        after_reg_rate = (sum(1 for r in after_regression if r.get("passed", False)) / len(after_regression) * 100) if after_regression else 0
        delta_reg = after_reg_rate - before_reg_rate
        symbol_reg = "✓" if delta_reg >= 0 else "✗"
        print(f"Regression: {before_reg_rate:.0f}% → {after_reg_rate:.0f}% {symbol_reg} ({delta_reg:+.0f}%)")

    if before_capability or after_capability:
        before_cap_rate = (sum(1 for r in before_capability if r.get("passed", False)) / len(before_capability) * 100) if before_capability else 0
        after_cap_rate = (sum(1 for r in after_capability if r.get("passed", False)) / len(after_capability) * 100) if after_capability else 0
        delta_cap = after_cap_rate - before_cap_rate
        symbol_cap = "✓" if delta_cap >= 0 else "✗"
        print(f"Capability: {before_cap_rate:.0f}% → {after_cap_rate:.0f}% {symbol_cap} ({delta_cap:+.1f}%)")

    print()
    print(f"Pass rate:  {before_rate:.0f}% → {after_rate:.0f}%  ({after_rate - before_rate:+.0f}%)")
    print(f"耗时:       {before_avg:.1f}s → {after_avg:.1f}s  ({after_avg - before_avg:+.1f}s)")
    print()

    # 按 case_id 对比
    before_map = {r["case"]["id"]: r for r in before_results}
    after_map = {r["case"]["id"]: r for r in after_results}

    for case_id in set(before_map.keys()) | set(after_map.keys()):
        before = before_map.get(case_id)
        after = after_map.get(case_id)

        if not before:
            print(f"{case_id}   NEW")
        elif not after:
            print(f"{case_id}   REMOVED")
        else:
            before_status = "PASS" if before.get("passed") else "FAIL"
            after_status = "PASS" if after.get("passed") else "FAIL"

            if before_status != after_status:
                symbol = "✓" if after_status == "PASS" else "✗"
                print(f"{case_id}   {before_status} → {after_status}  {symbol}")

                # 工具链变化
                before_tools = before.get("tool_names", [])
                after_tools = after.get("tool_names", [])
                if before_tools != after_tools:
                    print(f"  工具链: {before_tools} → {after_tools}")

                # 失败原因变化
                before_failures = before.get("failures", [])
                after_failures = after.get("failures", [])
                if before_failures and not after_failures:
                    print(f"  失败原因消失: {before_failures[0]}")
                elif after_failures and not before_failures:
                    print(f"  新增失败原因: {after_failures[0]}")
            else:
                print(f"{case_id}   {before_status} → {after_status}  (unchanged)")


# ============================================================================
# mine 命令
# ============================================================================

def cmd_mine(args):
    """Mine 命令入口"""
    from .tracer import LOG_DIR, sessions_from_logs, read_logs_for_session, extract_events

    log_dir = Path(args.log_dir) if args.log_dir else LOG_DIR

    # 使用索引获取所有 sessions（支持大文件）
    print("📦 扫描日志文件...")
    all_sessions = sessions_from_logs(log_dir)

    if not all_sessions:
        print("✗ 未找到 session")
        return

    # 过滤成功的 session
    successful_sessions = []
    for session in all_sessions:
        if session["tool_count"] >= args.min_tools and session["turns"] > 0:
            successful_sessions.append(session)

    if not successful_sessions:
        print("✗ 未找到符合条件的 session")
        return

    print(f"📦 从 {len(successful_sessions)} 个 session 提取用例")

    # 读取已有 cases（去重）
    existing_messages = set()
    output_file = Path(args.output) if args.output else Path("mined_cases.yaml")
    if output_file.exists():
        try:
            import yaml
            with open(output_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and "cases" in data:
                    for case in data.get("cases", []):
                        existing_messages.add(case.get("message", ""))
        except:
            pass

    # 提取新 cases
    new_cases = []
    for session in successful_sessions:
        session_id = session["session_id"]

        # 读取该 session 的日志
        entries = read_logs_for_session(log_dir, session_id)
        events = extract_events(entries, session_id)

        # 提取 message
        message = None
        for entry in entries:
            if "user_message" in entry:
                message = entry["user_message"]
                break
            elif "input" in entry and isinstance(entry["input"], str):
                message = entry["input"]
                break
            elif "prompt" in entry:
                message = entry["prompt"]
                break

        if not message or message in existing_messages:
            continue

        # 提取工具序列
        tool_names = [e.tool for e in events if e.kind == "tool_end"]

        case = {
            "id": f"mined_{session_id[:8]}",
            "message": message,
            "expect_tools": list(dict.fromkeys(tool_names)),  # 去重保序
            "expect_tools_ordered": tool_names,
            "tags": ["mined"],
            "description": f"从 session {session_id[:8]} 提取，时间 {session['last_ts'][:10]}"
        }

        new_cases.append(case)
        existing_messages.add(message)

    if not new_cases:
        print("✓ 没有新的 cases 需要添加")
        return

    # 写入文件
    output_data = {"cases": new_cases}

    try:
        import yaml
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, allow_unicode=True, default_flow_style=False)
        print(f"✓ 已生成 {len(new_cases)} 个用例: {output_file}")
    except ImportError:
        print("✗ 需要安装 PyYAML: pip install pyyaml")
        sys.exit(1)


# ============================================================================
# export 命令
# ============================================================================

def cmd_export(args):
    """Export 命令入口 - 导出 golden dataset"""
    from .tracer import LOG_DIR, read_all_logs, _is_tool_end, _is_turn_end

    log_dir = Path(args.log_dir) if args.log_dir else LOG_DIR
    workspace = get_workspace(args.workspace)

    # 读取日志（会自动跳过大文件）
    print("📦 扫描日志文件...")
    entries = read_all_logs(log_dir)

    if not entries:
        print("✗ 未找到日志条目")
        return

    # 手动聚合 sessions
    sessions_dict = defaultdict(lambda: {
        "session_id": "",
        "first_ts": "",
        "last_ts": "",
        "tool_count": 0,
        "turns": 0,
        "agent": "",
    })

    for entry in entries:
        session_id = entry.get("session_id", "")
        if not session_id:
            continue

        session = sessions_dict[session_id]
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

    sessions = list(sessions_dict.values())

    # 加载 merge report（如果有）
    merge_data = {}
    if args.merge_report and Path(args.merge_report).exists():
        with open(args.merge_report, 'r', encoding='utf-8') as f:
            report_results = json.load(f)
            for r in report_results:
                if r.get("passed"):
                    message = r["case"]["message"]
                    merge_data[message] = r.get("final_output", "")

    # 过滤成功的 session
    successful_sessions = [s for s in sessions if s["tool_count"] >= args.min_tools and s["turns"] > 0]

    if not successful_sessions:
        print("✗ 未找到符合条件的 session")
        return

    print(f"📦 从 {len(successful_sessions)} 个 session 导出 golden dataset")

    # 第一遍：收集所有 session 的数据并按 skill 分组
    session_data_list = []
    skill_to_tools = defaultdict(set)  # skill_triggered -> 该 skill 下所有 session 用过的工具集合

    for session in successful_sessions:
        session_id = session["session_id"]

        # 读取该 session 的日志
        from .tracer import read_logs_for_session
        entries = read_logs_for_session(log_dir, session_id)
        events = extract_events(entries, session_id)

        # 提取 user message
        user_message = None
        for entry in entries:
            for key in ["user_message", "input", "prompt"]:
                if key in entry and isinstance(entry[key], str):
                    user_message = entry[key]
                    break
            if user_message:
                break

        if not user_message:
            continue

        # 构建 golden_tool_sequence
        golden_tools = []
        for event in events:
            if event.kind == "tool_end":
                golden_tools.append({
                    "name": event.tool,
                    "args": event.input,
                    "output_summary": event.output[:200] if event.output else ""
                })

        # 获取 golden_output
        golden_output = ""
        golden_output_source = "log"
        for event in reversed(events):
            if event.kind == "llm_response":
                golden_output = event.output
                break

        # 尝试从 merge report 获取更准确的输出
        if user_message in merge_data:
            golden_output = merge_data[user_message]
            golden_output_source = "report"

        # 匹配 skill
        tool_names = [t["name"] for t in golden_tools]
        skill_triggered = None
        skills_dir = workspace / "skills"
        if skills_dir.exists():
            for skill_file in skills_dir.glob("*.md"):
                skill_name = skill_file.stem.replace("_", "").replace("-", "")
                for tool in tool_names:
                    tool_clean = tool.replace("_", "").replace("-", "")
                    if skill_name in tool_clean or tool_clean in skill_name:
                        skill_triggered = f"skills/{skill_file.name}"
                        break
                if skill_triggered:
                    break

        # 记录数据
        session_data = {
            "session": session,
            "session_id": session_id,
            "user_message": user_message,
            "golden_tools": golden_tools,
            "tool_names": tool_names,
            "golden_output": golden_output,
            "golden_output_source": golden_output_source,
            "skill_triggered": skill_triggered
        }
        session_data_list.append(session_data)

        # 按 skill 分组收集工具
        skill_key = skill_triggered if skill_triggered else "__no_skill__"
        skill_to_tools[skill_key].update(tool_names)

    # 第二遍：生成 records，包含 not_tool_called
    records = []
    for session_data in session_data_list:
        session_id = session_data["session_id"]
        session = session_data["session"]
        user_message = session_data["user_message"]
        golden_tools = session_data["golden_tools"]
        tool_names = session_data["tool_names"]
        golden_output = session_data["golden_output"]
        golden_output_source = session_data["golden_output_source"]
        skill_triggered = session_data["skill_triggered"]

        # 生成 assert
        asserts = []
        for tool in tool_names:
            asserts.append({"type": "tool_called", "value": tool})
        if len(tool_names) > 1:
            asserts.append({"type": "tool_order", "value": tool_names, "strict": False})

        # 生成 tool_args 断言
        for tool_data in golden_tools:
            if tool_data["args"]:
                asserts.append({
                    "type": "tool_args",
                    "tool": tool_data["name"],
                    "args": tool_data["args"]
                })

        # 简单词频提取关键词
        if golden_output:
            words = golden_output.split()
            word_freq = Counter(w for w in words if len(w) > 2)
            top_keywords = [w for w, _ in word_freq.most_common(3)]
            for kw in top_keywords:
                asserts.append({"type": "contains", "value": kw})

        # 生成 not_tool_called
        skill_key = skill_triggered if skill_triggered else "__no_skill__"
        all_tools_in_skill = skill_to_tools[skill_key]

        # 只有当同类 session 数量 > 1 时才生成 not_tool_called
        if len([s for s in session_data_list if (s["skill_triggered"] if s["skill_triggered"] else "__no_skill__") == skill_key]) > 1:
            # 同类 session 用过但当前 session 没用的工具
            forbidden_tools = all_tools_in_skill - set(tool_names)
            for tool in sorted(forbidden_tools):
                asserts.append({"type": "not_tool_called", "value": tool})

        # 构建记录
        record = {
            "id": f"{session_id[:8]}_1",
            "description": f"从 session {session_id[:8]} 提取，{session['last_ts'][:10]}",
            "source": "mined",
            "tags": ["mined"],
            "conversation": [
                {
                    "turn": 1,
                    "user": user_message,
                    "golden_tool_sequence": golden_tools,
                    "golden_output": golden_output,
                    "assert": asserts
                }
            ],
            "metadata": {
                "session_id": session_id,
                "agent": session.get("agent", "openclaw_agent"),
                "extracted_at": datetime.now().isoformat(),
                "skill_triggered": skill_triggered,
                "golden_output_source": golden_output_source
            }
        }

        records.append(record)

    # 输出
    output_file = Path(args.output)

    if args.format == "csv":
        # CSV 格式
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "description", "user", "golden_tools", "golden_output",
                "skill_triggered", "session_id", "extracted_at"
            ])
            writer.writeheader()

            for record in records:
                conv = record["conversation"][0]
                tools_str = ", ".join(t["name"] for t in conv["golden_tool_sequence"])
                writer.writerow({
                    "id": record["id"],
                    "description": record["description"],
                    "user": conv["user"],
                    "golden_tools": tools_str,
                    "golden_output": conv["golden_output"][:200],
                    "skill_triggered": record["metadata"]["skill_triggered"] or "",
                    "session_id": record["metadata"]["session_id"],
                    "extracted_at": record["metadata"]["extracted_at"]
                })

        print(f"✓ 已导出 {len(records)} 条记录到 CSV: {output_file}")

    else:
        # JSONL 格式
        with open(output_file, 'w', encoding='utf-8') as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        print(f"✓ 已导出 {len(records)} 条记录到 JSONL: {output_file}")


# ============================================================================
# 主入口
# ============================================================================

def cmd_edd(args):
    """EDD 命令分发"""
    if args.edd_cmd == "suggest":
        cmd_suggest(args)
    elif args.edd_cmd == "apply":
        cmd_apply(args)
    elif args.edd_cmd == "diff":
        cmd_diff(args)
    elif args.edd_cmd == "mine":
        cmd_mine(args)
    elif args.edd_cmd == "judge":
        cmd_judge(args)
    elif args.edd_cmd == "export":
        cmd_export(args)


# ============================================================================
# judge 命令
# ============================================================================

def cmd_judge(args):
    """Judge 命令入口 - 用 LLM 对 tool 选择和 output 质量打分"""
    import os

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"✗ 报告文件不存在: {args.report}")
        sys.exit(1)

    with open(report_path, 'r', encoding='utf-8') as f:
        results = json.load(f)

    # 初始化 LLM client
    provider = getattr(args, 'provider', 'anthropic')

    if provider == "anthropic":
        try:
            from anthropic import Anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                print("✗ 未设置 ANTHROPIC_API_KEY 环境变量")
                sys.exit(1)
            client = Anthropic(api_key=api_key)
            client_type = "anthropic"
        except ImportError:
            print("✗ 需要安装 anthropic: pip install anthropic")
            sys.exit(1)
    elif provider == "openai":
        try:
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print("✗ 未设置 OPENAI_API_KEY 环境变量")
                sys.exit(1)
            client = OpenAI(api_key=api_key)
            client_type = "openai"
        except ImportError:
            print("✗ 需要安装 openai: pip install openai")
            sys.exit(1)
    elif provider == "deepseek":
        try:
            from openai import OpenAI
            api_key = os.environ.get("DEEPSEEK_API_KEY")
            if not api_key:
                print("✗ 未设置 DEEPSEEK_API_KEY 环境变量")
                sys.exit(1)
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            client_type = "openai"
        except ImportError:
            print("✗ 需要安装 openai: pip install openai")
            sys.exit(1)
    else:
        print(f"✗ 不支持的提供商: {provider}")
        sys.exit(1)

    print(f"📊 使用 LLM 评估 {len(results)} 个测试结果...")
    print(f"提供商: {provider}")
    print(f"模型: {args.model}\n")

    judged_results = []

    for i, result in enumerate(results, 1):
        case_id = result["case"]["id"]
        message = result["case"]["message"]
        tool_names = result.get("tool_names", [])
        final_output = result.get("final_output", "")
        passed = result.get("passed", False)

        print(f"[{i}/{len(results)}] 评估 {case_id}...")

        # 构建 prompt
        prompt = f"""请评估以下 AI Agent 的执行结果：

用户输入: {message}

工具调用序列: {tool_names}

最终输出: {final_output}

测试状态: {"通过" if passed else "失败"}

请从以下维度打分（0-10分）：
1. 工具选择合理性：选择的工具是否合适、必要
2. 工具调用顺序：工具调用的顺序是否合理
3. 输出质量：输出是否准确、完整、有用
4. 整体表现：综合评价

请以 JSON 格式返回：
{{
  "tool_selection_score": <0-10>,
  "tool_order_score": <0-10>,
  "output_quality_score": <0-10>,
  "overall_score": <0-10>,
  "reasoning": "<简短评价>"
}}"""

        try:
            # 调用 LLM API
            if client_type == "anthropic":
                response = client.messages.create(
                    model=args.model,
                    max_tokens=1024,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                response_text = response.content[0].text
            else:  # openai or deepseek
                response = client.chat.completions.create(
                    model=args.model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1024
                )
                response_text = response.choices[0].message.content

            # 尝试提取 JSON
            import re
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                judgment = json.loads(json_match.group(0))
            else:
                # 如果没有找到 JSON，尝试直接解析整个响应
                judgment = json.loads(response_text)

            result_copy = result.copy()
            result_copy["llm_judgment"] = {
                **judgment,
                "model": args.model,
                "provider": provider,
                "raw_response": response_text
            }
            judged_results.append(result_copy)

            print(f"  ✓ 综合得分: {judgment.get('overall_score', 'N/A')}/10")

        except Exception as e:
            print(f"  ✗ 评估失败: {e}")
            result_copy = result.copy()
            result_copy["llm_judgment"] = {"error": str(e)}
            judged_results.append(result_copy)

    # 输出统计
    print("\n" + "─" * 60)
    print("📊 评估统计")
    print("─" * 60)

    valid_judgments = [r for r in judged_results if "llm_judgment" in r and "overall_score" in r["llm_judgment"]]
    if valid_judgments:
        avg_overall = sum(r["llm_judgment"]["overall_score"] for r in valid_judgments) / len(valid_judgments)
        avg_tool_selection = sum(r["llm_judgment"]["tool_selection_score"] for r in valid_judgments) / len(valid_judgments)
        avg_tool_order = sum(r["llm_judgment"]["tool_order_score"] for r in valid_judgments) / len(valid_judgments)
        avg_output_quality = sum(r["llm_judgment"]["output_quality_score"] for r in valid_judgments) / len(valid_judgments)

        print(f"平均综合得分: {avg_overall:.1f}/10")
        print(f"平均工具选择: {avg_tool_selection:.1f}/10")
        print(f"平均工具顺序: {avg_tool_order:.1f}/10")
        print(f"平均输出质量: {avg_output_quality:.1f}/10")

    # 保存结果
    output_path = Path(args.output) if args.output else report_path.with_suffix('.judged.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(judged_results, f, indent=2, ensure_ascii=False)

    print(f"\n✓ 评估报告已保存: {output_path}")
