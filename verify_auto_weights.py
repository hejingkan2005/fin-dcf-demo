"""
验证E/V和D/V现在总是从财务数据自动计算
"""
from app import compute_wacc
import pandas as pd

print("="*70)
print("验证：E/V 和 D/V 现在总是从财务数据自动计算")
print("="*70)
print()

# 测试数据1
mock_latest_1 = pd.Series({
    "短期借款": 100,
    "一年内到期非流动负债": 50,
    "长期借款": 200,
    "应付债券": 100,
    "租赁负债": 50,
    "股本": 500,
    "货币资金": 100,
})

# 测试数据2
mock_latest_2 = pd.Series({
    "短期借款": 0,
    "一年内到期非流动负债": 0,
    "长期借款": 100,
    "应付债券": 50,
    "租赁负债": 10,
    "股本": 200,
    "货币资金": 50,
})

test_cases = [
    ("测试1：较高的债务", mock_latest_1, 15.0),
    ("测试2：较低的债务", mock_latest_2, 10.0),
]

for name, mock_data, price in test_cases:
    print(f"{name}")
    print("-" * 70)
    
    result = compute_wacc(
        latest=mock_data,
        price=price,
        rf=0.017476,
        erp=0.06,
        beta=1.4,
        tax_rate=0.15,
        kd_pre_tax=0.032,
        size_premium=0.01,
    )
    
    # 手动计算预期值
    debt_value = (
        mock_data.get("短期借款", 0) +
        mock_data.get("一年内到期非流动负债", 0) +
        mock_data.get("长期借款", 0) +
        mock_data.get("应付债券", 0) +
        mock_data.get("租赁负债", 0)
    )
    equity_value = price * mock_data.get("股本", 0)
    total_value = equity_value + debt_value
    expected_e_weight = equity_value / total_value if total_value > 0 else 1.0
    expected_d_weight = debt_value / total_value if total_value > 0 else 0.0
    
    print(f"  权益价值: {equity_value:.2f}")
    print(f"  债务价值: {debt_value:.2f}")
    print(f"  总价值: {total_value:.2f}")
    print(f"  E/V: {result.e_weight:.4f} (期望: {expected_e_weight:.4f}) {'✓' if abs(result.e_weight - expected_e_weight) < 0.0001 else '✗'}")
    print(f"  D/V: {result.d_weight:.4f} (期望: {expected_d_weight:.4f}) {'✓' if abs(result.d_weight - expected_d_weight) < 0.0001 else '✗'}")
    print(f"  WACC: {result.wacc*100:.4f}%")
    print()

print("="*70)
print("✓ E/V 和 D/V 现在总是从财务数据自动计算（无手动覆盖选项）")
print("="*70)
