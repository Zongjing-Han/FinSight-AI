import os
import pandas as pd
import requests
import argparse
from pathlib import Path
import json

from sec_client import fetch_company_facts
from config import COMPANY_CONFIGS
from financial_data import (
    extract_annual_revenue,
    calculate_revenue_growth,
    revenue_to_records,
)
from reporting import render_revenue_table
from revenue_service import (
    get_company_revenue,
    select_recent_revenue,
)




def extract_msft_annual_revenue(facts: dict) -> pd.DataFrame:
    """使用微软配置提取年度收入。"""
    return extract_annual_revenue(
        facts,
        revenue_tag="RevenueFromContractWithCustomerExcludingAssessedTax",
        fiscal_end_month=6,
    )





def main():
    parser = argparse.ArgumentParser(
        description="提取公司年度营业收入并计算同比增长率"
    )

    parser.add_argument(
        "--ticker",
        type=str.upper,
        choices=COMPANY_CONFIGS.keys(),
        default="MSFT",
        help="公司股票代码，默认MSFT",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="忽略本地缓存，从 SEC 重新获取数据",
    )
    args = parser.parse_args()

    ticker = args.ticker
    config = COMPANY_CONFIGS[ticker]

    try:
        data = fetch_company_facts(
            config["cik"],
            refresh=args.refresh,
        )
    except requests.exceptions.Timeout:
        parser.exit(
            status=1,
            message="请求 SEC 超时，请稍后重试。\n",
        )
    except requests.exceptions.HTTPError as error:
        status_code = error.response.status_code
        parser.exit(
            status=1,
            message=(
                f"SEC 返回 HTTP {status_code}。"
                "请检查 User-Agent 配置及访问限制。\n"
            ),
        )
    except requests.exceptions.RequestException as error:
        parser.exit(
            status=1,
            message=f"无法完成 SEC 请求：{error}\n",
        )
    except ValueError as error:
        parser.exit(
            status=1,
            message=f"配置或响应数据错误：{error}\n",
        )

    print("公司名称：", data["entityName"])

    print("CIK：", data["cik"])

    print("数据分类：", list(data["facts"].keys()))

    annual_df = extract_annual_revenue(
        data,
        revenue_tag=config["revenue_tag"],
        fiscal_end_month=config["fiscal_end_month"],
    )

    print(f"\n{ticker}年度营业收入：")

    print(
        annual_df[
            ["fiscal_year", "start", "end", "val", "filed"]
        ].to_string(index=False)
    )

    annual_df = calculate_revenue_growth(annual_df)

    print(f"\n{ticker}年度收入及同比增长率（收入单位：十亿美元）：")

    print(
        annual_df[
            ["fiscal_year", "revenue_usd_billions", "revenue_growth_pct"]
        ].to_string(
            index=False,
            float_format=lambda value: f"{value:.2f}",
            na_rep="N/A",
        )
    )

    output_dir = Path(__file__).resolve().parent / "data"

    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"{ticker.lower()}_annual_revenue.csv"

    annual_df["ticker"] = ticker

    annual_df["cik"] = str(data["cik"]).zfill(10)

    annual_df["revenue_tag"] = config["revenue_tag"]

    annual_df["unit"] = "USD"

    accession_without_dashes = annual_df["accn"].str.replace(
        "-", "", regex=False
    )

    annual_df["source_url"] = (
        "https://www.sec.gov/Archives/edgar/data/"
        + str(int(data["cik"]))
        + "/"
        + accession_without_dashes
        + "/"
    )

    print("\n最近三年的收入及来源：")

    print(
        annual_df[
            ["fiscal_year", "val", "revenue_growth_pct", "source_url"]
        ].tail(3).to_string(index=False)
    )

    annual_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"\n结果已保存至：{output_path}")

    report = {
        "ticker": ticker,
        "company_name": data["entityName"],
        "cik": str(data["cik"]).zfill(10),
        "unit": "USD",
        "revenue_tag": config["revenue_tag"],
        "disclosure_policy": "latest_filed",
        "annual_revenue": revenue_to_records(annual_df),
    }

    json_path = output_dir / f"{ticker.lower()}_annual_revenue.json"

    json_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    print(f"JSON 结果已保存至：{json_path}")    


if __name__ == "__main__":
    main()
