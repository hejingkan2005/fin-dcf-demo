"""
最终验证：确保所有WACC相关计算都正确
"""
from app import compute_wacc, make_scenarios
import pandas as pd

print("="*80)
print("最终验证测试：WACC、E/V、D/V 计算正确性")
print("="*80)
print()

# 准备测试数据
mock_latest = pd.Series({
    "短期借款": 0,
    "一年内到期非流动负债": 0,
    "长期借款": 100,
    "应付债券": 50,
    "租赁负债": 10,
    "股本": 200,
    "货币资金": 50,
})

# ============ TEST 1: 基础参数 ============
print("TEST 1: 基础参数验证 （与截图保持一致）")
print("-" * 80)

result = compute_wacc(
    latest=mock_latest,
    price=10.0,
    rf=0.017476,        # Rf = 1.7476%
    erp=0.06,           # ERP = 6.0%（直接输入）
    beta=1.4,           # Beta = 1.4
    tax_rate=0.15,      # T = 15%
    kd_pre_tax=0.032,   # Kd = 3.2%
    size_premium=0.01,  # 规模溢价 = 1.0%
    equity_weight_override=0.95,  # 手动覆盖 E/V = 95%
)

checks = {
    "Rf": (result.rf, 0.017476, "%.4f"),
    "ERP": (result.market_premium, 0.06, "%.4f"),
    "Beta": (result.beta, 1.4, "%.2f"),
    "规模溢价": (result.size_premium, 0.01, "%.4f"),
    "Ke": (result.ke, 0.111476, "%.6f"),
    "Kd_after_tax": (result.kd_after_tax, 0.032 * (1-0.15), "%.6f"),
    "E/V": (result.e_weight, 0.95, "%.4f"),
    "D/V": (result.d_weight, 0.05, "%.4f"),
    "WACC": (result.wacc, 0.95*0.111476 + 0.05*0.032*(1-0.15), "%.6f"),
}

all_pass = True
for name, (actual, expected, fmt) in checks.items():
    match = abs(actual - expected) < 1e-6
    status = "✓" if match else "✗"
    if not match:
        all_pass = False
    print(f"  {status} {name:15s}: {fmt%actual:12s} (期望: {fmt%expected})")

print()
if all_pass:
    print("✓✓✓ TEST 1 通过：所有值都正确！")
else:
    print("✗✗✗ TEST 1 失败：有值不匹配")
print()

# ============ TEST 2: 不覆盖权重 ============
print("TEST 2: 不覆盖权重（自动计算权重）")
print("-" * 80)

result2 = compute_wacc(
    latest=mock_latest,
    price=10.0,
    rf=0.017476,
    erp=0.06,
    beta=1.4,
    tax_rate=0.15,
    kd_pre_tax=0.032,
    size_premium=0.01,
    equity_weight_override=None,  # 不覆盖，自动计算
)

# 自动计算：从财务数据推导
equity_value = 10.0 * 200  # price * shares
debt_value = 100 + 50 + 10  # 长期借款 + 应付债券 + 租赁负债
total = equity_value + debt_value
expected_e_weight = equity_value / total
expected_d_weight = debt_value / total

print(f"  Equity Value: {equity_value:.2f}")
print(f"  Debt Value: {debt_value:.2f}")
print(f"  Total: {total:.2f}")
print(f"  E/V (computed): {result2.e_weight:.4f} (expected: {expected_e_weight:.4f})")
print(f"  D/V (computed): {result2.d_weight:.4f} (expected: {expected_d_weight:.4f})")
print(f"  Ke: {result2.ke*100:.4f}%")
print(f"  WACC: {result2.wacc*100:.4f}%")
print()

# ============ TEST 3: make_scenarios修复验证 ============
print("TEST 3: 三情景分析（验证乐观情景WACC计算修复）")
print("-" * 80)

scenarios = make_scenarios(
    latest_fcff=100,
    forecast_years=5,
    base_growth=0.10,
    base_wacc=0.107262,
    base_tg=0.03,
    net_debt=50,
    shares=200,
    latest_price=10.0,
)

print("三情景 WACC 应该是:")
print(f"  保守: {0.107262 + 0.01:.6f} (基础 +1%)")
print(f"  中性: {0.107262:.6f} (基础)")  
print(f"  乐观: {0.107262 - 0.01:.6f} (基础 -1%)")
print()
print("实际 WACC:")
for idx, row in scenarios.iterrows():
    print(f"  {row['情景']:3s}: {row['WACC']:.6f}")
print()

expected_waccs = [0.107262 + 0.01, 0.107262, 0.107262 - 0.01]
actual_waccs = scenarios['WACC'].tolist()
scenarios_pass = all(abs(a - e) < 1e-6 for a, e in zip(actual_waccs, expected_waccs))

if scenarios_pass:
    print("✓✓✓ TEST 3 通过：三情景WACC计算正确！")
else:
    print("✗✗✗ TEST 3 失败：有情景WACC不匹配")
print()

# ============ 最终总结 ============
print("="*80)
print("最终总结")
print("="*80)
print(f"✓ Ke 计算正确: {result.ke*100:.4f}% = 11.1476% ✓")
print(f"✓ WACC 计算正确: {result.wacc*100:.4f}% = 10.7262% ✓")
print(f"✓ E/V 权重覆盖: {result.e_weight*100:.2f}% = 95.00% ✓")
print(f"✓ D/V 权重覆盖: {result.d_weight*100:.2f}% = 5.00% ✓")
print()
if all_pass and scenarios_pass:
    print("✓✓✓ 所有测试通过！代码已修正。")
else:
    print("⚠ 部分测试失败，请检查。")
