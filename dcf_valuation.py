import argparse
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import akshare as ak
import numpy as np
import pandas as pd


@dataclass
class DCFResult:
    code: str
    name: str
    report_dates: List[str]
    wacc: float
    terminal_growth: float
    forecast_years: int
    assumed_fcf_growth: float
    latest_fcff: float
    enterprise_value: float
    net_debt: float
    equity_value: float
    shares_outstanding: float
    intrinsic_value_per_share: float
    latest_market_price: Optional[float]
    upside_vs_market: Optional[float]


def cn_code_to_ak(code: str) -> str:
    code = code.strip()
    if code.startswith(("sz", "sh", "bj")):
        return code
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sz{code}"


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.replace("--", "", regex=False), errors="coerce")


def pick_col(df: pd.DataFrame, candidates: List[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    raise KeyError(f"Missing required columns: {candidates}")


def load_annual_5y_reports(ak_code: str) -> Dict[str, pd.DataFrame]:
    income = ak.stock_financial_report_sina(stock=ak_code, symbol="利润表")
    balance = ak.stock_financial_report_sina(stock=ak_code, symbol="资产负债表")
    cashflow = ak.stock_financial_report_sina(stock=ak_code, symbol="现金流量表")

    for df in (income, balance, cashflow):
        df["报告日"] = pd.to_datetime(df["报告日"], errors="coerce")

    def annual(df: pd.DataFrame) -> pd.DataFrame:
        out = df[df["报告日"].dt.month.eq(12) & df["报告日"].dt.day.eq(31)].copy()
        out = out.sort_values("报告日").drop_duplicates(subset=["报告日"], keep="last")
        return out.tail(5)

    income = annual(income)
    balance = annual(balance)
    cashflow = annual(cashflow)

    if min(len(income), len(balance), len(cashflow)) < 5:
        raise ValueError("可用年度财报不足 5 年，无法执行要求的 5 年 DCF。")

    return {"income": income, "balance": balance, "cashflow": cashflow}


def build_financial_panel(reports: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    income = reports["income"].copy()
    balance = reports["balance"].copy()
    cashflow = reports["cashflow"].copy()

    rev_col = pick_col(income, ["营业总收入", "营业收入"])
    np_col = pick_col(income, ["归属于母公司所有者的净利润", "净利润"])

    cfo_col = pick_col(cashflow, ["经营活动产生的现金流量净额", "经营活动产生的现金流量"])
    capex_col = pick_col(cashflow, ["购建固定资产、无形资产和其他长期资产所支付的现金"])

    equity_col = pick_col(balance, ["归属于母公司股东权益合计", "股东权益合计"])
    assets_col = pick_col(balance, ["资产总计"])
    liab_col = pick_col(balance, ["负债合计"])
    cash_col = pick_col(balance, ["货币资金"])
    shares_col = pick_col(balance, ["实收资本(或股本)"])

    panel = pd.DataFrame({
        "报告日": income["报告日"],
        "营业总收入": to_numeric(income[rev_col]),
        "归母净利润": to_numeric(income[np_col]),
        "经营现金流净额": to_numeric(cashflow[cfo_col]),
        "资本开支": to_numeric(cashflow[capex_col]),
        "归母股东权益": to_numeric(balance[equity_col]),
        "资产总计": to_numeric(balance[assets_col]),
        "负债合计": to_numeric(balance[liab_col]),
        "货币资金": to_numeric(balance[cash_col]),
        "股本": to_numeric(balance[shares_col]),
        "短期借款": to_numeric(balance["短期借款"]) if "短期借款" in balance.columns else 0.0,
        "一年内到期非流动负债": to_numeric(balance["一年内到期的非流动负债"]) if "一年内到期的非流动负债" in balance.columns else 0.0,
        "长期借款": to_numeric(balance["长期借款"]) if "长期借款" in balance.columns else 0.0,
        "应付债券": to_numeric(balance["应付债券"]) if "应付债券" in balance.columns else 0.0,
        "租赁负债": to_numeric(balance["租赁负债"]) if "租赁负债" in balance.columns else 0.0,
    })

    panel = panel.sort_values("报告日").reset_index(drop=True)
    panel["FCFF"] = panel["经营现金流净额"] - panel["资本开支"]

    panel["ROE"] = panel["归母净利润"] / panel["归母股东权益"]
    panel["资产负债率"] = panel["负债合计"] / panel["资产总计"]
    panel["净利率"] = panel["归母净利润"] / panel["营业总收入"]
    panel["FCFF利润率"] = panel["FCFF"] / panel["营业总收入"]

    return panel


def estimate_growth(panel: pd.DataFrame) -> float:
    fcff = panel["FCFF"].replace([np.inf, -np.inf], np.nan).dropna()
    if len(fcff) >= 2 and fcff.iloc[0] > 0 and fcff.iloc[-1] > 0:
        years = len(fcff) - 1
        cagr = (fcff.iloc[-1] / fcff.iloc[0]) ** (1 / years) - 1
    else:
        rev = panel["营业总收入"].replace([np.inf, -np.inf], np.nan).dropna()
        if len(rev) >= 2 and rev.iloc[0] > 0 and rev.iloc[-1] > 0:
            years = len(rev) - 1
            cagr = (rev.iloc[-1] / rev.iloc[0]) ** (1 / years) - 1
        else:
            cagr = 0.08

    # Keep assumptions in a conservative, explainable range.
    return float(np.clip(cagr, 0.03, 0.20))


def dcf_valuation(
    panel: pd.DataFrame,
    code: str,
    name: str,
    wacc: float,
    terminal_growth: float,
    forecast_years: int,
) -> DCFResult:
    latest = panel.iloc[-1]
    fcf_growth = estimate_growth(panel)

    fcff0 = float(latest["FCFF"])
    projected_fcff = [fcff0 * ((1 + fcf_growth) ** year) for year in range(1, forecast_years + 1)]

    pv_fcff = sum(val / ((1 + wacc) ** idx) for idx, val in enumerate(projected_fcff, start=1))
    terminal_value = projected_fcff[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1 + wacc) ** forecast_years)

    enterprise_value = pv_fcff + pv_terminal

    debt_cols = ["短期借款", "一年内到期非流动负债", "长期借款", "应付债券", "租赁负债"]
    interest_bearing_debt = float(latest[debt_cols].fillna(0).sum())
    cash = float(latest["货币资金"])
    net_debt = interest_bearing_debt - cash

    equity_value = enterprise_value - net_debt

    shares = float(latest["股本"])
    if shares <= 0:
        raise ValueError("无法从资产负债表提取有效股本，DCF 每股估值无法计算。")
    intrinsic_per_share = equity_value / shares

    latest_price = None
    upside = None
    try:
        ak_code = cn_code_to_ak(code)
        spot = ak.stock_zh_a_daily(symbol=ak_code, adjust="")
        latest_price = float(spot.iloc[-1]["close"])
        upside = intrinsic_per_share / latest_price - 1
    except Exception:
        latest_price = None
        upside = None

    return DCFResult(
        code=code,
        name=name,
        report_dates=[d.strftime("%Y-%m-%d") for d in panel["报告日"]],
        wacc=wacc,
        terminal_growth=terminal_growth,
        forecast_years=forecast_years,
        assumed_fcf_growth=fcf_growth,
        latest_fcff=fcff0,
        enterprise_value=float(enterprise_value),
        net_debt=float(net_debt),
        equity_value=float(equity_value),
        shares_outstanding=float(shares),
        intrinsic_value_per_share=float(intrinsic_per_share),
        latest_market_price=latest_price,
        upside_vs_market=upside,
    )


def format_money(value: float) -> str:
    return f"{value:,.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="基于近5年财报的A股DCF估值示例")
    parser.add_argument("--code", default="300502", help="A股代码，如 300502")
    parser.add_argument("--name", default="新易盛", help="股票名称，仅用于展示")
    parser.add_argument("--wacc", type=float, default=0.11, help="贴现率 WACC，默认 0.11")
    parser.add_argument("--terminal-growth", type=float, default=0.03, help="永续增长率，默认 0.03")
    parser.add_argument("--forecast-years", type=int, default=5, help="显式预测年数，默认 5")
    parser.add_argument("--save-prefix", default="output", help="输出文件前缀，默认 output")
    args = parser.parse_args()

    if args.terminal_growth >= args.wacc:
        raise ValueError("terminal_growth 必须小于 wacc，否则戈登增长模型无效。")

    ak_code = cn_code_to_ak(args.code)
    reports = load_annual_5y_reports(ak_code)
    panel = build_financial_panel(reports)

    result = dcf_valuation(
        panel=panel,
        code=args.code,
        name=args.name,
        wacc=args.wacc,
        terminal_growth=args.terminal_growth,
        forecast_years=args.forecast_years,
    )

    print("\n===== DCF 估值结果 =====")
    print(f"标的: {result.name} ({result.code})")
    print(f"财报区间: {result.report_dates[0]} ~ {result.report_dates[-1]}")
    print(f"假设: WACC={result.wacc:.2%}, 永续增长={result.terminal_growth:.2%}, FCF增长={result.assumed_fcf_growth:.2%}")
    print(f"最新FCFF: {format_money(result.latest_fcff)}")
    print(f"企业价值EV: {format_money(result.enterprise_value)}")
    print(f"净债务(Net Debt): {format_money(result.net_debt)}")
    print(f"股权价值Equity: {format_money(result.equity_value)}")
    print(f"股本(股): {result.shares_outstanding:,.0f}")
    print(f"DCF每股内在价值: {result.intrinsic_value_per_share:,.2f}")

    if result.latest_market_price is not None:
        print(f"最新收盘价: {result.latest_market_price:,.2f}")
        print(f"相对空间: {result.upside_vs_market:.2%}")
    else:
        print("最新市场价: 获取失败（不影响DCF内在价值计算）")

    metrics_display = panel[["报告日", "营业总收入", "归母净利润", "经营现金流净额", "资本开支", "FCFF", "ROE", "资产负债率", "净利率", "FCFF利润率"]].copy()
    metrics_display["报告日"] = metrics_display["报告日"].dt.strftime("%Y-%m-%d")
    print("\n===== 近5年核心指标 =====")
    print(metrics_display.to_string(index=False))

    panel_out = f"{args.save_prefix}_financial_panel.csv"
    json_out = f"{args.save_prefix}_dcf_result.json"

    panel.to_csv(panel_out, index=False, encoding="utf-8-sig")
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, ensure_ascii=False, indent=2)

    print(f"\n已输出: {panel_out}, {json_out}")


if __name__ == "__main__":
    main()
