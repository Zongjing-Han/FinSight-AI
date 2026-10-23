from config import COMPANY_CONFIGS
from financial_data import (
    calculate_revenue_growth,
    extract_annual_revenue,
    revenue_to_records,
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
