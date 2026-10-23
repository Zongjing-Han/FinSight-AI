import os
import pandas as pd
import requests
import argparse
from pathlib import Path
import json

COMPANY_CONFIGS = {
    "MSFT": {
        "cik": "0000789019",
        "revenue_tag": (
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ),
        "fiscal_end_month": 6,
    },
    "AAPL": {
        "cik": "0000320193",
        "revenue_tag": (
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ),
        "fiscal_end_month": 9,
    },
}




def fetch_company_facts(cik: str) -> dict:
    """从 SEC 获取指定公司的 Company Facts 数据。"""
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        raise ValueError("请先设置 SEC_USER_AGENT 环境变量")

    url = (
        "https://data.sec.gov/api/xbrl/companyfacts/"
        f"CIK{cik.zfill(10)}.json"
    )

    response = requests.get(
        url,
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def extract_msft_annual_revenue(facts: dict) -> pd.DataFrame:
    """使用微软配置提取年度收入。"""
    return extract_annual_revenue(
        facts,
        revenue_tag="RevenueFromContractWithCustomerExcludingAssessedTax",
        fiscal_end_month=6,
    )


def calculate_revenue_growth(
    annual_revenue: pd.DataFrame,
) -> pd.DataFrame:
    """计算连续财年的收入同比，返回新表。"""

    result = (
        annual_revenue
        .copy()
        .sort_values("fiscal_year")
        .reset_index(drop=True)
    )

    previous_revenue = result["val"].shift(1)
    previous_year = result["fiscal_year"].shift(1)

    can_compare = (
        (result["fiscal_year"] - previous_year == 1)
        & (previous_revenue > 0)
    )

    result["revenue_growth_pct"] = (
        (result["val"] / previous_revenue - 1) * 100
    ).where(can_compare)

    result["revenue_usd_billions"] = (
        result["val"] / 1_000_000_000
    )

    return result

def extract_annual_revenue(
    facts: dict,
    revenue_tag: str,
    fiscal_end_month: int,
) -> pd.DataFrame:
    """提取常规完整财年的收入，适用于当前验证的公司。"""

    financial_facts = facts["facts"]["us-gaap"]

    if revenue_tag not in financial_facts:
        raise ValueError(f"公司数据中不存在收入标签：{revenue_tag}")

    records = financial_facts[revenue_tag].get("units", {}).get("USD", [])
    if not records:
        raise ValueError("该收入标签没有美元记录")

    df = pd.DataFrame(records)

    # 即使某一列完全不存在，也创建为空值列
    required_columns = [
        "start", "end", "filed", "val", "accn", "form"
    ]
    df = df.reindex(
        columns=list(dict.fromkeys([*df.columns, *required_columns]))
    )

    for column in ["start", "end", "filed"]:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    df["val"] = pd.to_numeric(df["val"], errors="coerce")
    df = df.dropna(subset=required_columns).copy()

    # 包含起止两天：52 周为 364 天，53 周为 371 天
    period_days = (df["end"] - df["start"]).dt.days + 1

    annual_mask = (
        df["form"].isin(["10-K", "10-K/A"])
        & period_days.between(364, 371)
        & (df["end"].dt.month == fiscal_end_month)
    )

    result = (
        df.loc[annual_mask]
        .sort_values(["filed", "accn"])
        .drop_duplicates(subset=["start", "end"], keep="last")
        .sort_values("end")
        .reset_index(drop=True)
    )

    if result.empty:
        raise ValueError("没有找到符合筛选条件的年度收入")

    result["fiscal_year"] = result["end"].dt.year
    result["revenue_tag"] = revenue_tag

    return result

def revenue_to_records(
    revenue_df: pd.DataFrame,
) -> list[dict]:
    """把年度收入表转为可用于 JSON 的记录列表。"""
    columns = [
        "fiscal_year",
        "val",
        "revenue_growth_pct",
        "source_url",
    ]

    records = []

    for row in revenue_df[columns].to_dict(orient="records"):
        records.append({
            "fiscal_year": int(row["fiscal_year"]),
            "revenue": int(row["val"]),
            "growth_pct": (
                None
                if pd.isna(row["revenue_growth_pct"])
                else float(row["revenue_growth_pct"])
            ),
            "source_url": row["source_url"],
        })

    return records

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

def render_revenue_table(report: dict) -> str:
    """将收入报告渲染成 Markdown 表格，金额单位为亿美元。"""
    lines = [
        f"### {report['ticker']} 年度营业收入",
        "",
        "| 财年 | 营业收入（亿美元） | 同比增长率（%） | 来源 |",
        "|---|---:|---:|---|",
    ]

    records = sorted(
        report["annual_revenue"],
        key=lambda row: row["fiscal_year"],
    )

    for row in records:
        year = row["fiscal_year"]
        revenue = row["revenue"] / 100_000_000
        growth = row["growth_pct"]

        growth_text = (
            "无法计算"
            if growth is None
            else f"{growth:.2f}"
        )

        source = (
            f"[{year}财年收入来源]"
            f"({row['source_url']})"
        )

        lines.append(
            f"| {year} | {revenue:.2f} | {growth_text} | {source} |"
        )

    lines.extend([
        "",
        "来源链接指向 SEC 申报目录；历史数据按最新披露口径展示。",
    ])

    if report["returned_years"] < report["requested_years"]:
        missing = report["requested_years"] - report["returned_years"]
        lines.extend([
            "",
            f"请求 {report['requested_years']} 个财年，"
            f"当前工具返回 {report['returned_years']} 个，"
            f"少于请求数量 {missing} 个。"
            "这反映当前工具及收入标签的覆盖范围，"
            "不代表公司没有更早的财报。",
        ])

    return "\n".join(lines)



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
    args = parser.parse_args()

    ticker = args.ticker
    config = COMPANY_CONFIGS[ticker]

    try:
        data = fetch_company_facts(config["cik"])
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
