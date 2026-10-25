import pandas as pd

from config import COMPANY_CONFIGS
from sec_client import fetch_company_facts

from financial_data import (
    extract_annual_revenue,
    extract_annual_metric,
    calculate_net_margin,
)


for ticker, config in COMPANY_CONFIGS.items():
    facts = fetch_company_facts(config["cik"])
    financial_facts = facts["facts"]["us-gaap"]

    tag = "NetIncomeLoss"
    concept = financial_facts.get(tag)

    print(f"\n{'=' * 50}")
    print("公司：", ticker, facts["entityName"])

    if concept is None:
        print(f"未找到标签：{tag}")
        continue

    print("标签：", tag)
    print("名称：", concept.get("label"))
    print("说明：", concept.get("description"))

    records = concept.get("units", {}).get("USD", [])
    if not records:
        print("没有美元记录")
        continue

    df = pd.DataFrame(records)

    for column in ["start", "end", "filed"]:
        df[column] = pd.to_datetime(
            df[column],
            errors="coerce",
        )

    # 先观察年报中的记录，尚未筛选完整年度或去重
    annual_filings = df[
        df["form"].isin(["10-K", "10-K/A"])
    ].sort_values(["end", "filed"])

    print(
        annual_filings[
            ["start", "end", "val", "form", "filed", "accn"]
        ].tail(10).to_string(index=False)
    )

    revenue_df = extract_annual_revenue(
        facts,
        revenue_tag=config["revenue_tag"],
        fiscal_end_month=config["fiscal_end_month"],
    )

    net_income_df = extract_annual_metric(
        facts,
        tag="NetIncomeLoss",
        fiscal_end_month=config["fiscal_end_month"],
    )

    margins = calculate_net_margin(
        revenue_df,
        net_income_df,
    )

    print("\n最近三个收入财年的净利率核对：")

    # 以收入期间为基准，保留缺少净利润的情况
    recent = margins[
        margins["revenue"].notna()
    ].tail(3).copy()

    recent["revenue_usd_millions"] = (
        recent["revenue"] / 1_000_000
    )
    recent["net_income_usd_millions"] = (
        recent["net_income"] / 1_000_000
    )

    print(
        recent[[
            "fiscal_year",
            "start",
            "end",
            "revenue_usd_millions",
            "net_income_usd_millions",
            "net_margin_pct",
            "period_match",
            "revenue_accn",
            "net_income_accn",
        ]].to_string(
            index=False,
            float_format=lambda value: f"{value:.2f}",
            na_rep="N/A",
        )
    )