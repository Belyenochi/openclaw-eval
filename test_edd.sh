#!/bin/bash
# openclaw-edd 功能测试脚本

set -e

echo "=== openclaw-edd 功能测试 ==="
echo

# 设置别名
EDD="python3 -m src.openclaw_edd.cli"

# 1. 测试 gen-cases
echo "1. 测试 gen-cases..."
$EDD gen-cases --output test_cases.yaml --force
echo "✓ gen-cases 通过"
echo

# 2. 测试 sessions
echo "2. 测试 sessions..."
$EDD sessions --limit 5 > /dev/null
echo "✓ sessions 通过"
echo

# 3. 测试 trace
echo "3. 测试 trace..."
$EDD trace --session test123 > /dev/null
echo "✓ trace 通过"
echo

# 4. 测试 state
echo "4. 测试 state..."
$EDD state --session test123 --format json > /dev/null
echo "✓ state 通过"
echo

# 5. 测试 artifacts
echo "5. 测试 artifacts..."
$EDD artifacts > /dev/null
echo "✓ artifacts 通过"
echo

# 6. 测试 edd 子命令帮助
echo "6. 测试 edd 子命令..."
$EDD edd --help > /dev/null
echo "✓ edd 子命令通过"
echo

echo "=== 所有测试通过 ==="
