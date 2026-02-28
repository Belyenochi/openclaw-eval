#!/bin/bash
# 验证 Task 3 实现完整性

echo "=========================================="
echo "Task 3 实现验证"
echo "=========================================="
echo ""

# 1. 检查依赖
echo "[1/5] 检查依赖安装..."
if python -c "import anthropic" 2>/dev/null; then
    echo "✓ anthropic SDK 已安装"
else
    echo "✗ anthropic SDK 未安装"
    exit 1
fi

# 2. 检查 CLI 命令
echo ""
echo "[2/5] 检查 CLI 命令..."
if edd edd judge --help > /dev/null 2>&1; then
    echo "✓ judge 命令已注册"
else
    echo "✗ judge 命令未注册"
    exit 1
fi

# 3. 检查文档
echo ""
echo "[3/5] 检查文档..."
if [ -f "docs/JUDGE_COMMAND.md" ]; then
    echo "✓ JUDGE_COMMAND.md 文档存在"
else
    echo "✗ JUDGE_COMMAND.md 文档缺失"
    exit 1
fi

if [ -f "docs/TASK3_SUMMARY.md" ]; then
    echo "✓ TASK3_SUMMARY.md 总结存在"
else
    echo "✗ TASK3_SUMMARY.md 总结缺失"
    exit 1
fi

# 4. 检查测试文件
echo ""
echo "[4/5] 检查测试文件..."
if [ -f "test_judge.py" ]; then
    echo "✓ test_judge.py 存在"
else
    echo "✗ test_judge.py 缺失"
    exit 1
fi

if [ -f "test_judge_integration.py" ]; then
    echo "✓ test_judge_integration.py 存在"
else
    echo "✗ test_judge_integration.py 缺失"
    exit 1
fi

# 5. 运行集成测试
echo ""
echo "[5/5] 运行集成测试..."
if python test_judge_integration.py > /dev/null 2>&1; then
    echo "✓ 集成测试通过"
else
    echo "✗ 集成测试失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ 所有验证通过！"
echo "=========================================="
echo ""
echo "Task 3 实现完成："
echo "- ✅ Anthropic API 集成"
echo "- ✅ 多维度评分系统"
echo "- ✅ CLI 命令注册"
echo "- ✅ 完整文档"
echo "- ✅ 集成测试"
echo ""
echo "使用方法："
echo "  export ANTHROPIC_API_KEY=your_key"
echo "  edd edd judge --report test_report.json"
echo ""
echo "详细文档："
echo "  cat docs/JUDGE_COMMAND.md"
echo "  cat docs/TASK3_SUMMARY.md"
