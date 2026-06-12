from app import compute_wacc
import pandas as pd

# Mock latest financial data
latest = pd.Series({
    "短期借款": 0,
    "一年内到期非流动负债": 0,
    "长期借款": 100,
    "应付债券": 50,
    "租赁负债": 10,
    "股本": 200,
})

# 参数：与截图完全一致
rf = 0.017476
erp = 0.06
beta = 1.4
size_premium = 0.01
tax_rate = 0.15
kd_pre_tax = 0.032
price = 10.0

# 测试1：不使用覆盖权重（自动计算）
print("="*70)
print("测试1: 不覆盖权重（自动计算）")
print("="*70)
result1 = compute_wacc(latest, price, rf, erp, beta, tax_rate, kd_pre_tax, size_premium)
print(f"Ke: {result1.ke*100:.4f}%")
print(f"E/V: {result1.e_weight*100:.2f}%")
print(f"D/V: {result1.d_weight*100:.2f}%")
print(f"WACC: {result1.wacc*100:.4f}%")
print()

# 测试2：使用手动覆盖权重 E/V = 95%（与截图一致）
print("="*70)
print("测试2: 手动覆盖权重 E/V=95%, D/V=5% （与截图一致）")
print("="*70)
result2 = compute_wacc(latest, price, rf, erp, beta, tax_rate, kd_pre_tax, size_premium, equity_weight_override=0.95)
print(f"Ke: {result2.ke*100:.4f}%")
print(f"E/V: {result2.e_weight*100:.2f}%")
print(f"D/V: {result2.d_weight*100:.2f}%")
print(f"WACC: {result2.wacc*100:.4f}%")
print()

# 验证与截图的匹配
expected_wacc = 0.95 * 0.111476 + 0.05 * 0.032 * (1 - 0.15)
print(f"√ 手动计算预期 WACC: {expected_wacc*100:.4f}%")
print(f"√ 代码计算实际 WACC: {result2.wacc*100:.4f}%")
match = abs(result2.wacc - expected_wacc) < 0.00001
print(f"✓ 与截图完全匹配: {match}")
print()
print("="*70)
