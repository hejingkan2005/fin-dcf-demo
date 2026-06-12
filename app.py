from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import akshare as ak
import numpy as np
import pandas as pd
from flask import Flask, render_template, request

app = Flask(__name__)


@dataclass
class WaccBreakdown:
    rf: float
    market_return: float
    market_premium: float
    beta: float
    size_premium: float
    ke: float
    kd_pre_tax: float
    tax_rate: float
    kd_after_tax: float
    debt_value: float
    equity_value_market: float
    e_weight: float
    d_weight: float
    wacc: float


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
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("--", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def pick_col(df: pd.DataFrame, candidates: List[str]) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    raise KeyError(f"Missing required columns: {candidates}")


def resolve_ticker_and_name(user_input: str) -> Tuple[str, str]:
    value = user_input.strip()
    if not value:
        raise ValueError("请输入公司名称或6位股票代码。")

    mapping = ak.stock_info_a_code_name()
    mapping["code"] = mapping["code"].astype(str).str.zfill(6)
    mapping["name"] = mapping["name"].astype(str).str.strip()

    if value.isdigit() and len(value) == 6:
        row = mapping[mapping["code"] == value]
        if row.empty:
            raise ValueError(f"未找到股票代码: {value}")
        return value, str(row.iloc[0]["name"])

    exact = mapping[mapping["name"] == value]
    if not exact.empty:
        return str(exact.iloc[0]["code"]), str(exact.iloc[0]["name"])

    fuzzy = mapping[mapping["name"].str.contains(value, na=False)]
    if fuzzy.empty:
        raise ValueError(f"未找到名称包含 '{value}' 的A股公司。")

    return str(fuzzy.iloc[0]["code"]), str(fuzzy.iloc[0]["name"])


def load_annual_reports(ak_code: str) -> Dict[str, pd.DataFrame]:
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
        raise ValueError("可用年度财报不足5年，无法计算。")

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

    panel = pd.DataFrame(
        {
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
        }
    )

    panel = panel.sort_values("报告日").reset_index(drop=True)
    panel["FCFF"] = panel["经营现金流净额"] - panel["资本开支"]
    return panel


def estimate_fcf_growth(panel: pd.DataFrame) -> float:
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

    return float(np.clip(cagr, 0.03, 0.20))


def fetch_latest_10y_rf() -> float:
    rate_df = ak.bond_zh_us_rate()
    latest = to_numeric(rate_df["中国国债收益率10年"]).dropna().iloc[-1]
    return float(latest) / 100.0


def fetch_csi300_long_term_return() -> float:
    idx = ak.stock_zh_index_daily(symbol="sh000300").copy()
    idx["date"] = pd.to_datetime(idx["date"], errors="coerce")
    idx["close"] = to_numeric(idx["close"])
    idx = idx.dropna(subset=["date", "close"]).sort_values("date")
    if idx.empty:
        raise ValueError("无法获取沪深300指数数据。")

    first_close = float(idx.iloc[0]["close"])
    last_close = float(idx.iloc[-1]["close"])
    years = max((idx.iloc[-1]["date"] - idx.iloc[0]["date"]).days / 365.25, 1.0)
    return (last_close / first_close) ** (1 / years) - 1


def fetch_latest_price(ak_code: str) -> float:
    spot = ak.stock_zh_a_daily(symbol=ak_code, adjust="")
    return float(to_numeric(spot["close"]).dropna().iloc[-1])


def compute_wacc(
    latest: pd.Series,
    price: float,
    rf: float,
    erp: float,
    beta: float,
    tax_rate: float,
    kd_pre_tax: float,
    size_premium: float = 0.01,
) -> WaccBreakdown:
    debt_cols = ["短期借款", "一年内到期非流动负债", "长期借款", "应付债券", "租赁负债"]
    debt_value = float(latest[debt_cols].fillna(0).sum())
    shares = float(latest["股本"])
    equity_value_market = max(price * shares, 0.0)

    total_value = equity_value_market + debt_value
    if total_value <= 0:
        e_weight = 1.0
        d_weight = 0.0
    else:
        e_weight = equity_value_market / total_value
        d_weight = debt_value / total_value

    ke = rf + beta * erp + size_premium
    kd_after_tax = kd_pre_tax * (1 - tax_rate)
    wacc = e_weight * ke + d_weight * kd_after_tax

    return WaccBreakdown(
        rf=rf,
        market_return=rf + erp,
        market_premium=erp,
        beta=beta,
        size_premium=size_premium,
        ke=ke,
        kd_pre_tax=kd_pre_tax,
        tax_rate=tax_rate,
        kd_after_tax=kd_after_tax,
        debt_value=debt_value,
        equity_value_market=equity_value_market,
        e_weight=e_weight,
        d_weight=d_weight,
        wacc=wacc,
    )


def run_dcf(
    latest_fcff: float,
    forecast_years: int,
    fcff_growth: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares: float,
    latest_price: float,
) -> Dict[str, object]:
    fcffs = [latest_fcff * ((1 + fcff_growth) ** year) for year in range(1, forecast_years + 1)]
    pvs = [value / ((1 + wacc) ** year) for year, value in enumerate(fcffs, start=1)]
    pv_fcff_sum = float(sum(pvs))

    tv = fcffs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_tv = tv / ((1 + wacc) ** forecast_years)

    ev = pv_fcff_sum + pv_tv
    equity_value = ev - net_debt
    intrinsic_value = equity_value / shares
    upside = intrinsic_value / latest_price - 1

    return {
        "fcffs": fcffs,
        "pvs": pvs,
        "pv_fcff_sum": pv_fcff_sum,
        "tv": tv,
        "pv_tv": pv_tv,
        "ev": ev,
        "equity": equity_value,
        "intrinsic": intrinsic_value,
        "upside": upside,
    }


def yi(value: float) -> float:
    return value / 1e8


def make_scenarios(
    latest_fcff: float,
    forecast_years: int,
    base_growth: float,
    base_wacc: float,
    base_tg: float,
    net_debt: float,
    shares: float,
    latest_price: float,
) -> pd.DataFrame:
    scenario_inputs = [
        ("保守", max(base_growth - 0.03, 0.01), base_wacc + 0.01, max(base_tg - 0.005, 0.01)),
        ("中性", base_growth, base_wacc, base_tg),
        ("乐观", min(base_growth + 0.03, 0.30), base_wacc - 0.01, min(base_tg + 0.005, 0.05)),
    ]

    rows: List[Dict[str, float | str]] = []
    for name, growth, wacc, tg in scenario_inputs:
        if tg >= wacc:
            tg = max(wacc - 0.01, 0.005)

        dcf = run_dcf(
            latest_fcff=latest_fcff,
            forecast_years=forecast_years,
            fcff_growth=growth,
            wacc=wacc,
            terminal_growth=tg,
            net_debt=net_debt,
            shares=shares,
            latest_price=latest_price,
        )
        rows.append(
            {
                "情景": name,
                "FCFF增长率": growth,
                "WACC": wacc,
                "永续增长率": tg,
                "EV(亿元)": yi(float(dcf["ev"])),
                "股权价值(亿元)": yi(float(dcf["equity"])),
                "每股内在价值(元)": float(dcf["intrinsic"]),
                "相对空间": float(dcf["upside"]),
            }
        )

    return pd.DataFrame(rows)


@app.route("/", methods=["GET", "POST"])
def index():
    error: Optional[str] = None
    result: Optional[Dict[str, object]] = None

    defaults = {
        "query": "新易盛",
        "terminal_growth": 0.03,
        "beta": 1.4,
        "tax_rate": 0.15,
        "forecast_years": 5,
        "debt_cost": 0.032,
        "size_premium": 0.01,
        "erp": 0.06,
    }

    form = defaults.copy()
    try:
        form["rf_rate"] = fetch_latest_10y_rf()
    except Exception:
        form["rf_rate"] = 0.018

    if request.method == "POST":
        try:
            form["query"] = request.form.get("query", form["query"]).strip()
            form["terminal_growth"] = float(request.form.get("terminal_growth", form["terminal_growth"]))
            form["rf_rate"] = float(request.form.get("rf_rate", form["rf_rate"]))
            form["erp"] = float(request.form.get("erp", form["erp"]))
            form["beta"] = float(request.form.get("beta", form["beta"]))
            form["tax_rate"] = float(request.form.get("tax_rate", form["tax_rate"]))
            form["forecast_years"] = int(request.form.get("forecast_years", form["forecast_years"]))
            form["debt_cost"] = float(request.form.get("debt_cost", form["debt_cost"]))
            form["size_premium"] = float(request.form.get("size_premium", form["size_premium"]))

            if form["forecast_years"] < 1:
                raise ValueError("预测年数必须大于0。")

            code, name = resolve_ticker_and_name(form["query"])
            ak_code = cn_code_to_ak(code)

            reports = load_annual_reports(ak_code)
            panel = build_financial_panel(reports)
            latest = panel.iloc[-1]

            latest_price = fetch_latest_price(ak_code)
            latest_fcff = float(latest["FCFF"])
            fcff_growth = estimate_fcf_growth(panel)

            wacc_detail = compute_wacc(
                latest=latest,
                price=latest_price,
                rf=form["rf_rate"],
                erp=form["erp"],
                beta=form["beta"],
                tax_rate=form["tax_rate"],
                kd_pre_tax=form["debt_cost"],
                size_premium=form["size_premium"],
            )

            if form["terminal_growth"] >= wacc_detail.wacc:
                raise ValueError("永续增长率必须小于WACC。")

            debt_cols = ["短期借款", "一年内到期非流动负债", "长期借款", "应付债券", "租赁负债"]
            interest_debt = float(latest[debt_cols].fillna(0).sum())
            cash = float(latest["货币资金"])
            net_debt = interest_debt - cash
            shares = float(latest["股本"])

            dcf = run_dcf(
                latest_fcff=latest_fcff,
                forecast_years=form["forecast_years"],
                fcff_growth=fcff_growth,
                wacc=wacc_detail.wacc,
                terminal_growth=form["terminal_growth"],
                net_debt=net_debt,
                shares=shares,
                latest_price=latest_price,
            )

            step1_df = pd.DataFrame(
                {
                    "年份": [f"FCFF{idx}" for idx in range(1, form["forecast_years"] + 1)],
                    "FCFF(亿元)": [round(yi(v), 2) for v in dcf["fcffs"]],
                }
            )

            step2_df = pd.DataFrame(
                {
                    "年份": [f"PV{idx}" for idx in range(1, form["forecast_years"] + 1)],
                    "公式": [f"PV{idx} = FCFF{idx} / (1 + WACC)^{idx}" for idx in range(1, form["forecast_years"] + 1)],
                    "折现值(亿元)": [round(yi(v), 2) for v in dcf["pvs"]],
                }
            )

            scenario_df = make_scenarios(
                latest_fcff=latest_fcff,
                forecast_years=form["forecast_years"],
                base_growth=fcff_growth,
                base_wacc=wacc_detail.wacc,
                base_tg=form["terminal_growth"],
                net_debt=net_debt,
                shares=shares,
                latest_price=latest_price,
            )

            result = {
                "company": {"code": code, "name": name, "latest_price": latest_price},
                "params": {
                    "terminal_growth": form["terminal_growth"],
                    "rf_rate": form["rf_rate"],
                    "erp": form["erp"],
                    "beta": form["beta"],
                    "tax_rate": form["tax_rate"],
                    "forecast_years": form["forecast_years"],
                    "debt_cost": form["debt_cost"],
                    "fcff_growth": fcff_growth,
                },
                "wacc": wacc_detail,
                "step1": step1_df.to_dict(orient="records"),
                "step2": step2_df.to_dict(orient="records"),
                "step2_sum": yi(float(dcf["pv_fcff_sum"])),
                "step3_tv": yi(float(dcf["tv"])),
                "step4_pv_tv": yi(float(dcf["pv_tv"])),
                "step5_ev": yi(float(dcf["ev"])),
                "step6_net_debt": yi(net_debt),
                "step6_equity": yi(float(dcf["equity"])),
                "step7_intrinsic": float(dcf["intrinsic"]),
                "step8_upside": float(dcf["upside"]),
                "scenario_rows": scenario_df.round(4).to_dict(orient="records"),
                "report_dates": [d.strftime("%Y-%m-%d") for d in panel["报告日"]],
            }
        except Exception as exc:
            error = str(exc)

    return render_template("index.html", form=form, result=result, error=error)


if __name__ == "__main__":
    app.run(debug=True)
