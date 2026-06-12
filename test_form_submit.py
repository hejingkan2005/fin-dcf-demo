import re
from app import app

client = app.test_client()

# Test POST with specific parameters
form_data = {
    "query": "新易盛",
    "terminal_growth": 0.03,
    "rf_rate": 0.017476,  # 1.7476%
    "market_return": 0.09,  # 9%
    "beta": 1.4,
    "tax_rate": 0.15,
    "debt_cost": 0.032,  # 3.2%
    "size_premium": 0.01,  # 1%
    "forecast_years": 5,
}

print("提交的表单数据:")
for k, v in form_data.items():
    print(f"  {k}: {v}")
print()

try:
    response = client.post("/", data=form_data)
    print(f"Response Status: {response.status_code}")
    
    # Extract WACC value from HTML
    html = response.data.decode("utf-8")
    
    # Find WACC in KPI section
    kpi_match = re.search(r'<div class="title">WACC</div><div class="value">([^<]+)</div>', html)
    if kpi_match:
        wacc_display = kpi_match.group(1)
        print(f"KPI WACC显示: {wacc_display}")
    
    # Find WACC in detailed table
    table_match = re.search(r'<tr><td>WACC</td>.*?<strong>([^<]+)</strong>', html, re.DOTALL)
    if table_match:
        wacc_table = table_match.group(1)
        print(f"表格 WACC显示: {wacc_table}")
    
    # Extract all key values
    ke_match = re.search(r'股权成本 Ke.*?<td>([^<]+)</td>', html, re.DOTALL)
    if ke_match:
        print(f"Ke: {ke_match.group(1)}")
    
    e_weight_match = re.search(r'权益权重 E/V.*?<td>([^<]+)</td>', html, re.DOTALL)
    if e_weight_match:
        print(f"E/V: {e_weight_match.group(1)}")
    
    d_weight_match = re.search(r'债务权重 D/V.*?<td>([^<]+)</td>', html, re.DOTALL)
    if d_weight_match:
        print(f"D/V: {d_weight_match.group(1)}")
        
    # Check if there's an error
    error_match = re.search(r'<div class="error">([^<]+)</div>', html)
    if error_match:
        print(f"ERROR: {error_match.group(1)}")
    
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
