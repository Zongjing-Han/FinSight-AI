import pandas as pd


def extract_annual_metric(
    facts: dict,
    tag: str,
    fiscal_end_month: int,
) -> pd.DataFrame:
    """提取常规完整财年的美元指标，按最新披露口径去重。"""

    financial_facts = facts["facts"]["us-gaap"]

    if tag not in financial_facts:
        raise ValueError(f"公司数据中不存在指标标签：{tag}")

    records = financial_facts[tag].get("units", {}).get("USD", [])
    if not records:
        raise ValueError("该指标标签没有美元记录")

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
        raise ValueError("没有找到符合筛选条件的年度指标")

    result["fiscal_year"] = result["end"].dt.year
    result["metric_tag"] = tag

    return result

def extract_annual_revenue(
    facts: dict,
    revenue_tag: str,
    fiscal_end_month: int,
) -> pd.DataFrame:
    """提取年度营业收入，保留原有接口和字段。"""
    result = extract_annual_metric(
        facts,
        tag=revenue_tag,
        fiscal_end_month=fiscal_end_month,
    )

    return result.rename(
        columns={"metric_tag": "revenue_tag"}
    )

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

def calculate_net_margin(
    revenue_df: pd.DataFrame,
    net_income_df: pd.DataFrame,
) -> pd.DataFrame:
    """按完整会计期间对齐，计算归母净利润口径的净利率。"""
    columns = ["start", "end", "val", "filed", "accn"]

    revenue = revenue_df[columns].rename(columns={
        "val": "revenue",
        "filed": "revenue_filed",
        "accn": "revenue_accn",
    })

    net_income = net_income_df[columns].rename(columns={
        "val": "net_income",
        "filed": "net_income_filed",
        "accn": "net_income_accn",
    })

    result = revenue.merge(
        net_income,
        on=["start", "end"],
        how="outer",
        validate="one_to_one",
        indicator="period_match",
    )

    result = result.sort_values(
        ["end", "start"]
    ).reset_index(drop=True)

    result["fiscal_year"] = result["end"].dt.year

    can_calculate = (
        result["revenue"].notna()
        & (result["revenue"] > 0)
        & result["net_income"].notna()
    )

    result["net_margin_pct"] = (
        result["net_income"] / result["revenue"] * 100
    ).where(can_calculate)

    return result