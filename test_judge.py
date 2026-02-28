#!/usr/bin/env python
"""测试 judge 命令的基本功能"""
import json
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from openclaw_edd.edd import cmd_judge

class Args:
    def __init__(self):
        self.report = "test_report.json"
        self.output = "test_report.judged.json"
        self.model = "claude-3-5-sonnet-20241022"

# 测试参数解析和基本流程
args = Args()

# 检查报告文件是否存在
if not Path(args.report).exists():
    print(f"✗ 测试报告不存在: {args.report}")
    sys.exit(1)

print("✓ 测试报告文件存在")

# 读取报告
with open(args.report, 'r', encoding='utf-8') as f:
    results = json.load(f)
    print(f"✓ 成功读取 {len(results)} 个测试结果")

# 验证数据结构
for result in results:
    assert "case" in result
    assert "id" in result["case"]
    assert "message" in result["case"]
    print(f"✓ 测试用例 {result['case']['id']} 数据结构正确")

print("\n✓ 所有基本检查通过")
print("\n注意: 实际 LLM 调用需要设置 ANTHROPIC_API_KEY 环境变量")
print("使用方法: export ANTHROPIC_API_KEY=your_key && edd judge --report test_report.json")
