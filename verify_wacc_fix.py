from app import compute_wacc
import pandas as pd

# Mock latest financial data for testing
latest = pd.Series({
    "短期借款": 0,
    "一年内到期非流动负债": 0,
    "长期借款": 100,
    "应付债券": 50,
    "租赁负债": 10,
    "股本": 200,
})

# Test with screenshot values using NEW method
# ERP = 6.0% (directly input), size_premium = 1.0%
# Rf = 1.7476%
rf = 0.017476
erp = 0.06  # Market Risk Premium (direct input)
beta = 1.4
size_premium = 0.01
tax_rate = 0.15
kd_pre_tax = 0.032
price = 10.0  # arbitrary price

result = compute_wacc(latest, price, rf, erp, beta, tax_rate, kd_pre_tax, size_premium)

print("="*60)
print("WACC 计算核对（与截图比较）")
print("="*60)
print()
print(f"Rf (无风险利率): {result.rf*100:.4f}%")
print(f"ERP (市场风险溢价): {result.market_premium*100:.2f}%")
print(f"Beta: {result.beta}")
print(f"规模溢价: {result.size_premium*100:.2f}%")
print()
print(f"股权成本 Ke = Rf + β×ERP + 规模溢价")
print(f"           = {result.rf*100:.4f}% + {result.beta}×{result.market_premium*100:.2f}% + {result.size_premium*100:.2f}%")
print(f"           = {result.rf*100:.4f}% + {result.beta*result.market_premium*100:.2f}% + {result.size_premium*100:.2f}%")
print(f"           = {result.ke*100:.4f}%")
print()
print(f"√ 预期 Ke: 11.1476%")
print(f"√ 实际 Ke: {result.ke*100:.4f}%")
match_ke = abs(result.ke - 0.111476) < 0.00001
print(f"✓ Ke 匹配: {match_ke}")
print()
print("-"*60)
print()
print(f"Kd (税前债务成本): {result.kd_pre_tax*100:.2f}%")
print(f"税率 T: {result.tax_rate*100:.0f}%")
print(f"税后债务成本 Kd×(1-T): {result.kd_after_tax*100:.4f}%")
print()
print(f"权益权重 E/V: {result.e_weight*100:.2f}%")
print(f"债务权重 D/V: {result.d_weight*100:.2f}%")
print()

# 计算WACC
wacc = result.e_weight * result.ke + result.d_weight * result.kd_after_tax
print(f"WACC = (E/V)×Ke + (D/V)×Kd×(1-T)")
print(f"     = {result.e_weight:.4f}×{result.ke*100:.4f}% + {result.d_weight:.4f}×{result.kd_pre_tax*100:.2f}%×{1-result.tax_rate:.2f}")
print(f"     = {result.e_weight*result.ke*100:.4f}% + {result.d_weight*result.kd_after_tax*100:.4f}%")
print(f"     = {wacc*100:.4f}%")
print()
print(f"√ 预期 WACC: 10.7262%  (截图: 0.95×11.1476% + 0.05×3.2%×0.85)")
print(f"√ 实际 WACC: {result.wacc*100:.4f}%")
match_wacc = abs(result.wacc - 0.107262) < 0.00001
print(f"✓ WACC 匹配: {match_wacc}")
print()
print("="*60)
if match_ke and match_wacc:
    print("✓✓✓ 所有计算正确！")
else:
    print("⚠ 请检查上述计算")
print("="*60)
