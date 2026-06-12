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

# Test with screenshot values
# β = 1.4, market_premium = 6.0%, size_premium = 1.0%
# Rf = 1.7476%, Rm = 1.7476% + 6.0% = 7.7476%
rf = 0.017476
market_return = rf + 0.06  # market_premium = 6.0%
beta = 1.4
size_premium = 0.01
tax_rate = 0.15
kd_pre_tax = 0.032
price = 10.0  # arbitrary price

result = compute_wacc(latest, price, rf, market_return, beta, tax_rate, kd_pre_tax, size_premium)

print(f"Rf: {result.rf*100:.4f}%")
print(f"Market Return: {result.market_return*100:.4f}%")
print(f"Market Premium: {result.market_premium*100:.4f}%")
print(f"Beta: {result.beta}")
print(f"Size Premium: {result.size_premium*100:.2f}%")
print(f"Ke = Rf + β×(Rm-Rf) + Size Premium")
print(f"   = {result.rf*100:.4f}% + {result.beta}×{result.market_premium*100:.4f}% + {result.size_premium*100:.2f}%")
print(f"   = {result.ke*100:.4f}%")
print()
print(f"Expected Ke: 1.7476% + 1.4×6.0% + 1.0% = 11.1476%")
print()
print(f"Kd (pre-tax): {result.kd_pre_tax*100:.2f}%")
print(f"Tax Rate: {result.tax_rate*100:.0f}%")
print(f"Kd (after-tax): {result.kd_after_tax*100:.4f}%")
print(f"E/V: {result.e_weight*100:.2f}%")
print(f"D/V: {result.d_weight*100:.2f}%")
print()
print(f"WACC = (E/V)×Ke + (D/V)×Kd×(1-T)")
print(f"     = {result.e_weight:.4f}×{result.ke*100:.4f}% + {result.d_weight:.4f}×{result.kd_pre_tax*100:.2f}%×{1-result.tax_rate:.2f}")
print(f"     = {result.wacc*100:.4f}%")
print()
print(f"Expected WACC: 0.95×11.1476% + 0.05×3.2%×0.85 = 10.7262%")
