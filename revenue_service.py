import pandas as pd

from config import COMPANY_CONFIGS
from financial_data import (
    calculate_revenue_growth,
    extract_annual_revenue,
    revenue_to_records,
    extract_annual_metric,
    calculate_net_margin,
)
from sec_client import fetch_company_facts




def select_recent_revenue(report: dict, years: int) -> dict:
    """返回最近 N 个可用财年的收入，不修改原报告。"""
    if not 1 <= years <= 10:
        raise ValueError("years 必须在 1 到 10 之间")

    records = sorted(
        report["annual_revenue"],
        key=lambda record: record["fiscal_year"],
    )
    selected = records[-years:]

    return {
        **report,
        "annual_revenue": selected,
        "requested_years": years,
        "returned_years": len(selected),
        "selected_fiscal_years": [
            record["fiscal_year"] for record in selected
        ],
    }



def get_company_revenue(ticker: str) -> dict:
    """获取已支持公司的年度收入、同比增长率和来源。"""
    ticker = ticker.upper()

    if ticker not in COMPANY_CONFIGS:
        raise ValueError(f"暂不支持公司：{ticker}")

    config = COMPANY_CONFIGS[ticker]
    facts = fetch_company_facts(config["cik"])

    annual_df = extract_annual_revenue(
        facts,
        revenue_tag=config["revenue_tag"],
        fiscal_end_month=config["fiscal_end_month"],
    )
    annual_df = calculate_revenue_growth(annual_df)

    accession = annual_df["accn"].str.replace(
        "-", "", regex=False
    )
    annual_df["source_url"] = (
        "https://www.sec.gov/Archives/edgar/data/"
        + str(int(facts["cik"]))
        + "/"
        + accession
        + "/"
    )

    return {
        "ticker": ticker,
        "company_name": facts["entityName"],
        "cik": str(facts["cik"]).zfill(10),
        "unit": "USD",
        "revenue_tag": config["revenue_tag"],
        "disclosure_policy": "latest_filed",
        "annual_revenue": revenue_to_records(annual_df),
    }


def get_company_profitability(ticker: str) -> dict:
    """获取年度收入、归母净利润、净利率及各自来源。"""
    ticker = ticker.upper()

    if ticker not in COMPANY_CONFIGS:
        raise ValueError(f"暂不支持公司：{ticker}")

    config = COMPANY_CONFIGS[ticker]
    facts = fetch_company_facts(config["cik"])

    revenue = extract_annual_revenue(
        facts,
        revenue_tag=config["revenue_tag"],
        fiscal_end_month=config["fiscal_end_month"],
    )
    net_income = extract_annual_metric(
        facts,
        tag="NetIncomeLoss",
        fiscal_end_month=config["fiscal_end_month"],
    )

    combined = calculate_net_margin(revenue, net_income)

    # 展示以收入期间为基准，缺少净利润时仍保留该期间
    combined = combined[
        combined["revenue"].notna()
    ]

    def source_url(accession):
        if pd.isna(accession):
            return None

        return (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{int(facts['cik'])}/"
            f"{accession.replace('-', '')}/"
        )

    records = []

    for row in combined.to_dict(orient="records"):
        records.append({
            "fiscal_year": int(row["fiscal_year"]),
            "start": row["start"].date().isoformat(),
            "end": row["end"].date().isoformat(),
            "revenue": int(row["revenue"]),
            "net_income": (
                None
                if pd.isna(row["net_income"])
                else int(row["net_income"])
            ),
            "net_margin_pct": (
                None
                if pd.isna(row["net_margin_pct"])
                else float(row["net_margin_pct"])
            ),
            "period_match": str(row["period_match"]),
            "revenue_source_url": source_url(
                row["revenue_accn"]
            ),
            "net_income_source_url": source_url(
                row["net_income_accn"]
            ),
        })

    return {
        "ticker": ticker,
        "company_name": facts["entityName"],
        "unit": "USD",
        "revenue_tag": config["revenue_tag"],
        "net_income_tag": "NetIncomeLoss",
        "net_margin_definition": (
            "归属于母公司的税后净利润 / 营业收入 * 100%"
        ),
        "disclosure_policy": "latest_filed_per_metric",
        "annual_profitability": records,
    }