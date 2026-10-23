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