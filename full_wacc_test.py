"""
完整的WACC验证测试，使用截图中的所有参数
"""
from app import (
    compute_wacc, build_financial_panel, load_annual_reports,
    cn_code_to_ak, fetch_latest_price, resolve_ticker_and_name,
    WaccBreakdown
)
import pandas as pd

# 首先，让我们用模拟数据测试compute_wacc函数
print("="*70)
print("TEST 1: 完全手动的compute_wacc测试（模拟数据）")
print("="*70)

# 创建模拟财务数据
mock_latest = pd.Series({
    "短期借款": 0,
    "一年内到期非流动负债": 0,
    "长期借款": 100,
    "应付债券": 50,
    "租赁负债": 10,
    "股本": 200,
    "货币资金": 50,
})

# 测试参数（完全复现截图）
test_cases = [
    {
        "name": "不覆盖权重（自动计算）",
        "price": 10.0,
        "rf": 0.017476,
        "erp": 0.06,
        "beta": 1.4,
        "tax_rate": 0.15,
        "kd_pre_tax": 0.032,
        "size_premium": 0.01,
        "equity_weight_override": None,
    },
    {
        "name": "覆盖为E/V=95% D/V=5%（与截图一致）",
        "price": 10.0,
        "rf": 0.017476,
        "erp": 0.06,
        "beta": 1.4,
        "tax_rate": 0.15,
        "kd_pre_tax": 0.032,
        "size_premium": 0.01,
        "equity_weight_override": 0.95,
    },
]

for test_case in test_cases:
    name = test_case.pop("name")
    print(f"\n{name}")
    print("-" * 70)
    
    result = compute_wacc(mock_latest, **test_case)
    
    print(f"Rf:                    {result.rf*100:.4f}%")
    print(f"ERP:                   {result.market_premium*100:.4f}%")
    print(f"Beta:                  {result.beta:.2f}")
    print(f"Size Premium:          {result.size_premium*100:.4f}%")
    print(f"Ke = Rf + β×ERP + SP:  {result.rf*100:.4f}% + {result.beta:.2f}×{result.market_premium*100:.4f}% + {result.size_premium*100:.4f}%")
    print(f"                       = {result.ke*100:.4f}%")
    print()
    print(f"Kd (pre-tax):          {result.kd_pre_tax*100:.4f}%")
    print(f"Tax Rate:              {result.tax_rate*100:.2f}%")
    print(f"Kd (after-tax):        {result.kd_after_tax*100:.4f}%")
    print()
    print(f"E/V:                   {result.e_weight*100:.2f}%")
    print(f"D/V:                   {result.d_weight*100:.2f}%")
    print()
    print(f"WACC = (E/V)×Ke + (D/V)×Kd×(1-T)")
    print(f"     = {result.e_weight:.4f}×{result.ke*100:.4f}% + {result.d_weight:.4f}×{result.kd_after_tax*100:.4f}%")
    print(f"     = {result.e_weight*result.ke*100:.4f}% + {result.d_weight*result.kd_after_tax*100:.4f}%")
    print(f"     = {result.wacc*100:.4f}%")
    print()

# 验证与截图的预期值
print("="*70)
print("验证与截图预期值的匹配")
print("="*70)
print(f"预期 Ke:   11.1476%")
print(f"预期 WACC: 10.7262%  (E/V=95%, D/V=5%)")
print()

# 计算预期值
expected_ke = 0.017476 + 1.4 * 0.06 + 0.01
expected_wacc = 0.95 * expected_ke + 0.05 * 0.032 * (1 - 0.15)
print(f"手动计算 Ke:   {expected_ke*100:.4f}%")
print(f"手动计算 WACC: {expected_wacc*100:.4f}%")
print()

# 用代码计算
code_result = compute_wacc(
    mock_latest, 
    price=10.0,
    rf=0.017476, 
    erp=0.06,
    beta=1.4,
    tax_rate=0.15, 
    kd_pre_tax=0.032,
    size_premium=0.01,
    equity_weight_override=0.95
)
print(f"代码计算 Ke:   {code_result.ke*100:.4f}%  {'✓' if abs(code_result.ke - expected_ke) < 0.00001 else '✗'}")
print(f"代码计算 WACC: {code_result.wacc*100:.4f}%  {'✓' if abs(code_result.wacc - expected_wacc) < 0.00001 else '✗'}")
