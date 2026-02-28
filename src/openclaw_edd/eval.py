"""
Eval 命令实现

负责：
- run: 运行评测用例集
- gen-cases: 生成用例模板
"""

import json
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .models import EvalCase, EvalResult
from .tracer import read_logs_for_session, extract_events, _is_turn_end

# 内置用例
BUILTIN_CASES = [
    {
        "id": "weather_shanghai",
        "message": "今天上海天气怎么样",
        "expect_tools": ["get_weather"],
        "description": "天气查询基础验证"
    },
    {
        "id": "mysql_slow_query",
        "message": "MySQL 最近有慢查询吗",
        "expect_tools": ["query_metrics"],
        "description": "MySQL 慢查询检测"
    },
    {
        "id": "no_tool_chitchat",
        "message": "你好",
        "forbidden_tools": ["query_db", "execute_sql"],
        "description": "闲聊不应调用工具"
    },
]


def load_cases(cases_file: str = None) -> list[EvalCase]:
    """加载测试用例"""
    if not cases_file:
        return [EvalCase(**c) for c in BUILTIN_CASES]

    cases_path = Path(cases_file)

    # 支持 JSONL 格式（golden dataset）
    if cases_path.suffix == '.jsonl':
        try:
            cases = []
            with open(cases_path, 'r', encoding='utf-8') as f:
                for line in f:
                    record = json.loads(line)
                    # 从 golden dataset 格式转换为 EvalCase
                    for conv in record.get("conversation", []):
                        case_data = {
                            "id": record["id"],
                            "message": conv["user"],
                            "description": record.get("description", ""),
                            "tags": record.get("tags", []),
                        }
                        # 从 assert 提取期望
                        for assertion in conv.get("assert", []):
                            if assertion["type"] == "tool_called":
                                if "expect_tools" not in case_data:
                                    case_data["expect_tools"] = []
                                case_data["expect_tools"].append(assertion["value"])
                            elif assertion["type"] == "tool_order":
                                case_data["expect_tools_ordered"] = assertion["value"]
                                case_data["expect_tools_ordered_strict"] = assertion.get("strict", False)
                            elif assertion["type"] == "not_tool_called":
                                if "forbidden_tools" not in case_data:
                                    case_data["forbidden_tools"] = []
                                case_data["forbidden_tools"].append(assertion["value"])
                            elif assertion["type"] == "contains":
                                if "expect_output_contains" not in case_data:
                                    case_data["expect_output_contains"] = []
                                case_data["expect_output_contains"].append(assertion["value"])
                            elif assertion["type"] == "tool_args":
                                if "expect_tool_args" not in case_data:
                                    case_data["expect_tool_args"] = {}
                                tool_name = assertion["tool"]
                                case_data["expect_tool_args"][tool_name] = assertion["args"]

                        cases.append(EvalCase(**case_data))
            return cases
        except Exception as e:
            print(f"✗ 加载 JSONL 用例失败: {e}")
            sys.exit(1)

    # YAML 格式
    try:
        import yaml
        with open(cases_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return [EvalCase(**c) for c in data.get("cases", [])]
    except ImportError:
        print("✗ 需要安装 PyYAML: pip install pyyaml")
        sys.exit(1)
    except Exception as e:
        print(f"✗ 加载用例失败: {e}")
        sys.exit(1)


def send_message(agent: str, message: str, use_local: bool = False) -> str:
    """发送消息给 agent，返回 session_id"""
    try:
        cmd = ["openclaw", "agent", f"--agent={agent}", "--json", "--message", message]
        if use_local:
            cmd.insert(4, "--local")  # 在 --json 之前插入 --local

        # 增加超时时间，OpenClaw 处理可能需要较长时间
        timeout = 120 if use_local else 60

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # 检查命令是否成功执行
        if result.returncode != 0:
            print(f"⚠ openclaw 命令返回错误码: {result.returncode}")
            if result.stderr:
                print(f"   错误信息: {result.stderr[:200]}")
            return None

        # 解析 JSON 响应，提取 sessionId
        try:
            data = json.loads(result.stdout)
            # Gateway 模式: result.meta.agentMeta.sessionId
            session_id = data.get("result", {}).get("meta", {}).get("agentMeta", {}).get("sessionId")
            if session_id:
                return session_id
            # Local 模式: meta.agentMeta.sessionId
            session_id = data.get("meta", {}).get("agentMeta", {}).get("sessionId")
            if session_id:
                return session_id

            # 如果都没找到，打印调试信息
            print(f"⚠ 无法从响应中提取 sessionId")
            print(f"   响应结构: {list(data.keys())}")

        except json.JSONDecodeError as e:
            print(f"⚠ JSON 解析失败: {e}")
            print(f"   响应内容: {result.stdout[:200]}")

        return None
    except subprocess.TimeoutExpired:
        print(f"⚠ 发送消息超时（{timeout}秒）")
        return None
    except Exception as e:
        print(f"⚠ 发送消息失败: {e}")
        return None


def wait_for_completion(session_id: str, timeout_s: int, log_dir: str) -> bool:
    """等待 agent 完成"""
    start_time = time.time()
    last_line_count = 0
    stable_count = 0

    while time.time() - start_time < timeout_s:
        elapsed = int(time.time() - start_time)

        try:
            result = subprocess.run(
                ["openclaw", "logs", "--json", f"--session={session_id}", f"--since={elapsed}s"],
                capture_output=True,
                text=True,
                timeout=5
            )

            lines = result.stdout.strip().splitlines()

            # 检查完成标记
            for line in lines:
                from .tracer import parse_line
                entry = parse_line(line)
                if entry and _is_turn_end(entry):
                    return True

            # 检查稳定
            if len(lines) == last_line_count:
                stable_count += 1
                if stable_count >= 3:
                    return True
            else:
                stable_count = 0

            last_line_count = len(lines)

        except Exception:
            pass

        time.sleep(2)

    return False


def check_assertions(case: EvalCase, events: list, final_output: str) -> tuple[bool, list[str]]:
    """检查断言"""
    failures = []
    tool_names = [e.tool for e in events if e.kind == "tool_end"]

    # expect_tools
    if case.expect_tools:
        missing = set(case.expect_tools) - set(tool_names)
        if missing:
            failures.append(f"缺少必要工具调用: {', '.join(missing)}（实际: {tool_names}）")

    # expect_tools_ordered
    if case.expect_tools_ordered:
        if case.expect_tools_ordered_strict:
            # EXACT 模式：必须完全一致
            if tool_names != case.expect_tools_ordered:
                failures.append(f"工具调用顺序不符（strict模式）: 期望 {case.expect_tools_ordered}，实际 {tool_names}")
        else:
            # IN_ORDER 模式：期望工具必须按顺序出现，但允许中间穿插其他工具
            it = iter(tool_names)
            if not all(tool in it for tool in case.expect_tools_ordered):
                failures.append(f"工具调用顺序不符: 期望 {case.expect_tools_ordered}，实际 {tool_names}")

    # forbidden_tools
    if case.forbidden_tools:
        forbidden_used = set(case.forbidden_tools) & set(tool_names)
        if forbidden_used:
            failures.append(f"调用了禁止的工具: {', '.join(forbidden_used)}")

    # expect_output_contains
    if case.expect_output_contains:
        missing_keywords = [kw for kw in case.expect_output_contains if kw not in final_output]
        if missing_keywords:
            failures.append(f"输出缺少关键词: {', '.join(missing_keywords)}")

    # expect_tool_args
    if case.expect_tool_args:
        for tool_name, expected_args in case.expect_tool_args.items():
            # 找到该工具的实际调用 event
            actual_events = [e for e in events if e.kind == "tool_end" and e.tool == tool_name]
            if not actual_events:
                failures.append(f"工具未被调用，无法验证参数: {tool_name}")
                continue
            # 取最后一次调用
            actual_args = actual_events[-1].input
            for key, expected_val in expected_args.items():
                actual_val = actual_args.get(key)
                if str(actual_val) != str(expected_val):
                    failures.append(
                        f"工具参数不符: {tool_name}.{key} 期望={expected_val} 实际={actual_val}"
                    )

    return len(failures) == 0, failures


def run_eval_case(case: EvalCase, dry_run: bool, log_dir: str, use_local: bool = False, session_id_override: str = None) -> EvalResult:
    """运行单个测试用例"""
    start_time = time.time()
    session_id = session_id_override  # 使用提供的 session_id（用于 dry-run 测试）
    events = []
    final_output = ""

    if not dry_run:
        session_id = send_message(case.agent, case.message, use_local)
        if not session_id:
            return EvalResult(
                case=case,
                passed=False,
                events=[],
                final_output="",
                duration_s=time.time() - start_time,
                failures=["无法发送消息或获取 session_id"],
                timestamp=datetime.now().isoformat()
            )

        wait_for_completion(session_id, case.timeout_s, log_dir)

    # 提取事件
    if session_id:
        from .tracer import read_logs_for_session, extract_events
        entries = read_logs_for_session(Path(log_dir), session_id)
        events = extract_events(entries, session_id)

    # 获取最终输出
    for event in reversed(events):
        if event.kind == "llm_response":
            final_output = event.output
            break

    # 检查断言
    passed, failures = check_assertions(case, events, final_output)

    return EvalResult(
        case=case,
        passed=passed,
        events=events,
        final_output=final_output,
        duration_s=time.time() - start_time,
        failures=failures,
        session_id=session_id,
        timestamp=datetime.now().isoformat()
    )


def generate_html_report(results: list[EvalResult], output_file: str):
    """生成 HTML 报告"""
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OpenClaw EDD Report</title>
    <style>
        body {{ font-family: 'Monaco', 'Menlo', monospace; background: #1e1e1e; color: #d4d4d4; padding: 20px; }}
        h1 {{ color: #4ec9b0; }}
        .summary {{ background: #252526; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
        .case {{ background: #252526; padding: 15px; border-radius: 5px; margin-bottom: 15px; }}
        .pass {{ color: #4ec9b0; }}
        .fail {{ color: #f48771; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; }}
        .badge-pass {{ background: #4ec9b0; color: #1e1e1e; }}
        .badge-fail {{ background: #f48771; color: #1e1e1e; }}
        pre {{ background: #1e1e1e; padding: 10px; border-radius: 3px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>⚡ OpenClaw EDD Report</h1>
    <div class="summary">
        <strong>总计:</strong> {total_count} 用例<br>
        <strong>通过:</strong> <span class="pass">{passed_count}</span><br>
        <strong>失败:</strong> <span class="fail">{total_count - passed_count}</span><br>
        <strong>通过率:</strong> {pass_rate:.1f}%
    </div>
"""

    for result in results:
        status_class = "pass" if result.passed else "fail"
        badge_class = "badge-pass" if result.passed else "badge-fail"
        status_text = "PASS" if result.passed else "FAIL"

        html += f"""
    <div class="case">
        <h3>{result.case.id} <span class="badge {badge_class}">{status_text}</span></h3>
        <p><strong>消息:</strong> {result.case.message}</p>
        <p><strong>耗时:</strong> {result.duration_s:.2f}s</p>
        <p><strong>工具链:</strong> {', '.join(result.tool_names) if result.tool_names else '(无)'}</p>
"""

        if result.failures:
            html += "        <p><strong class='fail'>失败原因:</strong></p><ul>"
            for failure in result.failures:
                html += f"<li>{failure}</li>"
            html += "</ul>"

        if result.final_output:
            output_preview = result.final_output[:200]
            if len(result.final_output) > 200:
                output_preview += "..."
            html += f"        <p><strong>输出:</strong></p><pre>{output_preview}</pre>"

        html += "    </div>"

    html += """
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def cmd_run(args):
    """Run 命令入口"""
    # 加载用例
    if args.case:
        cases = [EvalCase(
            id="cli_case",
            message=args.case,
            expect_tools=args.expect_tools or [],
            forbidden_tools=args.forbidden_tools or [],
            agent=args.agent
        )]
    else:
        cases = load_cases(args.cases)

    # 过滤 tags
    if args.tags:
        tag_set = set(args.tags)
        cases = [c for c in cases if tag_set & set(c.tags)]

    if not cases:
        print("✗ 没有要运行的用例")
        sys.exit(1)

    print(f"⚡ OpenClaw Eval  —  {len(cases)} 用例\n")

    results = []
    for case in cases:
        print(f"→ {case.id}: {case.message}")

        result = run_eval_case(
            case,
            args.dry_run,
            args.log_dir,
            getattr(args, 'local', False),
            getattr(args, 'session', None)
        )
        results.append(result)

        if result.passed:
            print(f"  [✓ PASS] {result.duration_s:.1f}s")
        else:
            print(f"  [✗ FAIL] {result.duration_s:.1f}s")

        # 显示工具链
        if result.tool_names:
            print(f"  工具链: {', '.join(result.tool_names)}")
        else:
            print(f"  工具链: (无)")

        # 显示详细 trace（如果启用）
        if getattr(args, 'show_trace', False) and result.events:
            print(f"  \n  📋 详细 Trace:")
            for i, event in enumerate(result.events, 1):
                if event.kind == "tool_start":
                    print(f"    {i}. 🔧 {event.tool} 开始")
                    if event.input:
                        input_str = str(event.input)[:100]
                        if len(str(event.input)) > 100:
                            input_str += "..."
                        print(f"       输入: {input_str}")
                elif event.kind == "tool_end":
                    duration = f" ({event.duration_ms}ms)" if event.duration_ms else ""
                    print(f"    {i}. ✓ {event.tool} 完成{duration}")
                    if event.output:
                        output_str = str(event.output)[:100]
                        if len(str(event.output)) > 100:
                            output_str += "..."
                        print(f"       输出: {output_str}")
                elif event.kind == "llm_response":
                    output_str = event.output[:100]
                    if len(event.output) > 100:
                        output_str += "..."
                    print(f"    {i}. 💬 LLM 响应: {output_str}")
            print()

        # 显示最终输出（如果没有启用 trace）
        if not getattr(args, 'show_trace', False) and result.final_output:
            output_preview = result.final_output[:80]
            if len(result.final_output) > 80:
                output_preview += "..."
            print(f"  输出: {output_preview}")

        if result.failures:
            for failure in result.failures:
                print(f"  ✗ {failure}")

        print()

    # 汇总
    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0
    avg_duration = sum(r.duration_s for r in results) / total_count if total_count > 0 else 0

    # 按 eval_type 分组统计
    regression_results = [r for r in results if r.case.eval_type == "regression"]
    capability_results = [r for r in results if r.case.eval_type == "capability"]

    print("─" * 60)

    if regression_results:
        reg_passed = sum(1 for r in regression_results if r.passed)
        reg_total = len(regression_results)
        reg_rate = (reg_passed / reg_total * 100) if reg_total > 0 else 0
        print(f"📊 Regression Eval（防退步）")
        print("─" * 60)
        print(f"通过: {reg_passed}/{reg_total}  ({reg_rate:.0f}%)")
        if reg_rate < 100:
            print("  ⚠ 低于 100% 需要关注")
        failed_reg = [r for r in regression_results if not r.passed]
        if failed_reg:
            print(f"FAIL: {', '.join(r.case.id for r in failed_reg)}")
        print()

    if capability_results:
        cap_passed = sum(1 for r in capability_results if r.passed)
        cap_total = len(capability_results)
        cap_rate = (cap_passed / cap_total * 100) if cap_total > 0 else 0
        print(f"📈 Capability Eval（能力爬坡）")
        print("─" * 60)
        print(f"通过: {cap_passed}/{cap_total}  ({cap_rate:.0f}%)")
        print("  ℹ 正常，这是爬坡指标")
        passed_cap = [r for r in capability_results if r.passed]
        if passed_cap:
            print(f"PASS: {', '.join(r.case.id for r in passed_cap[:5])}")
            if len(passed_cap) > 5:
                print(f"      ... 还有 {len(passed_cap) - 5} 个")
        print()

    print("─" * 60)
    print(f"评测完成: {passed_count}/{total_count} 通过 ({pass_rate:.0f}%)")

    failed_cases = [r for r in results if not r.passed]
    if failed_cases:
        print(f"失败 {len(failed_cases)} 项:")
        for r in failed_cases:
            print(f"  - {r.case.id}: {r.failures[0] if r.failures else '未知错误'}")

    print(f"平均耗时: {avg_duration:.1f}s")

    # Baseline 对比
    if getattr(args, 'baseline', None):
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            print("\n" + "─" * 60)
            print("📊 Baseline 对比")
            print("─" * 60)

            try:
                with open(baseline_path, 'r', encoding='utf-8') as f:
                    baseline_results = json.load(f)

                # 计算 baseline 指标
                baseline_passed = sum(1 for r in baseline_results if r.get("passed", False))
                baseline_total = len(baseline_results)
                baseline_rate = (baseline_passed / baseline_total * 100) if baseline_total > 0 else 0
                baseline_avg = sum(r.get("duration_s", 0) for r in baseline_results) / baseline_total if baseline_total > 0 else 0

                # 对比
                rate_delta = pass_rate - baseline_rate
                time_delta = avg_duration - baseline_avg

                print(f"Pass rate:  {baseline_rate:.0f}% → {pass_rate:.0f}%  ({rate_delta:+.0f}%)")
                print(f"平均耗时:   {baseline_avg:.1f}s → {avg_duration:.1f}s  ({time_delta:+.1f}s)")

                # 按 case 对比
                baseline_map = {r["case"]["id"]: r for r in baseline_results}
                current_map = {r.case.id: r for r in results}

                print("\n详细变化:")
                for case_id in set(baseline_map.keys()) | set(current_map.keys()):
                    baseline = baseline_map.get(case_id)
                    current = current_map.get(case_id)

                    if not baseline:
                        print(f"  + {case_id}  NEW")
                    elif not current:
                        print(f"  - {case_id}  REMOVED")
                    else:
                        baseline_status = "PASS" if baseline.get("passed") else "FAIL"
                        current_status = "PASS" if current.passed else "FAIL"

                        if baseline_status != current_status:
                            symbol = "✓" if current_status == "PASS" else "✗"
                            print(f"  {symbol} {case_id}  {baseline_status} → {current_status}")

                            # 显示工具链变化
                            baseline_tools = baseline.get("tool_names", [])
                            current_tools = [e.tool for e in current.events if e.kind == "tool_end"]
                            if baseline_tools != current_tools:
                                print(f"     工具链: {baseline_tools} → {current_tools}")

            except Exception as e:
                print(f"⚠ 加载 baseline 失败: {e}")
        else:
            print(f"\n⚠ Baseline 文件不存在: {args.baseline}")

    # 输出报告
    if args.output_json:
        with open(args.output_json, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)
        print(f"\n✓ JSON 报告已保存: {args.output_json}")

    if args.output_html:
        generate_html_report(results, args.output_html)
        print(f"✓ HTML 报告已保存: {args.output_html}")

    # CI 集成
    if failed_cases:
        sys.exit(1)


def cmd_gen_cases(args):
    """Gen-cases 命令入口"""
    template = """# OpenClaw EDD 用例集
cases:
  - id: example_weather
    message: "今天上海天气怎么样"
    eval_type: regression          # "regression" (防退步) | "capability" (能力爬坡)，默认 regression
    expect_tools:
      - get_weather
    expect_output_contains:
      - "上海"
    agent: openclaw_agent
    timeout_s: 30
    tags: [smoke, weather]
    description: "天气查询基础验证"

  - id: example_forbidden
    message: "你好"
    eval_type: regression
    forbidden_tools:
      - query_db
      - execute_sql
    tags: [smoke]
    description: "闲聊不应调用工具"

  - id: example_ordered
    message: "查询数据库并分析结果"
    eval_type: regression
    expect_tools_ordered:
      - query_db
      - analyze_data
    # expect_tools_ordered_strict: false  # 默认 false（IN_ORDER模式）：允许中间有其他工具调用
    #                                     # 设为 true（EXACT模式）：实际工具序列必须和期望完全一致
    tags: [integration]
    description: "工具调用顺序验证"

  - id: example_tool_args
    message: "MySQL 最近一小时有慢查询吗"
    eval_type: regression
    expect_tools:
      - query_metrics
    expect_tool_args:              # 工具参数断言（White-box 评测）
      query_metrics:
        time_range: "1h"           # 精确匹配：实际调用必须包含此参数且值相等
        metric: "p99_latency"      # 未指定的参数不检查
    tags: [mysql, sre]
    description: "MySQL 慢查询排查（带参数验证）"

  - id: example_capability
    message: "预测 MySQL 未来一周的存储增长"
    eval_type: capability          # 能力爬坡用例，通过率从低开始
    expect_tools:
      - query_metrics
      - forecast
    tags: [mysql, advanced]
    description: "MySQL 容量预测（新能力）"
"""

    output_file = args.output or "cases.yaml"

    if Path(output_file).exists() and not args.force:
        print(f"✗ 文件已存在: {output_file}（使用 --force 覆盖）")
        sys.exit(1)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"✓ 用例模板已生成: {output_file}")
