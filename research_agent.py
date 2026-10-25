import asyncio
import os
import json

from revenue_service import (
    get_company_revenue,
    select_recent_revenue,
)
from reporting import render_revenue_table

from agents import Agent, Runner, function_tool

from revenue_service import (
    get_company_revenue,
    get_company_profitability,
    select_recent_revenue,
)

from reporting import (
    render_revenue_table,
    render_profitability_table,
)


@function_tool
def fetch_annual_revenue(ticker: str, years: int = 3) -> str:
    """获取公司最近 N 个已披露完整财年的收入、同比和来源。

    Args:
        ticker: 公司股票代码，仅支持 MSFT 或 AAPL。
        years: 返回最近几个财年，范围为 1 到 10，默认 3。
    """
    if not 1 <= years <= 10:
        raise ValueError("years 必须在 1 到 10 之间")

    result = select_recent_revenue(
        get_company_revenue(ticker), 
        years
    )

    print(
        f"[工具返回] {ticker} 财年："
        f"{result['selected_fiscal_years']}"
    )

    result["rendered_table"] = render_revenue_table(result)

    return json.dumps(
        result,
        ensure_ascii=False,
        allow_nan=False,
    )

@function_tool
def fetch_profitability(ticker: str, years: int = 3) -> str:
    """获取最近 N 个收入财年的归母净利润和净利率。

    Args:
        ticker: 公司股票代码，仅支持 MSFT 或 AAPL。
        years: 返回最近几个财年，范围为 1 到 10，默认 3。
    """
    if not 1 <= years <= 10:
        raise ValueError("years 必须在 1 到 10 之间")

    report = get_company_profitability(ticker)

    records = sorted(
        report["annual_profitability"],
        key=lambda row: (row["end"], row["start"]),
    )
    selected = records[-years:]

    report["annual_profitability"] = selected
    report["requested_years"] = years
    report["returned_years"] = len(selected)
    report["selected_fiscal_years"] = [
        row["fiscal_year"] for row in selected
    ]

    table = render_profitability_table(report)

    if len(selected) < years:
        table += (
            f"\n\n请求 {years} 个财年，当前工具返回 "
            f"{len(selected)} 个。这反映当前工具及标签的覆盖范围，"
            "不代表公司没有更早的财报。"
        )

    report["rendered_table"] = table

    print(
        f"[盈利能力工具] {report['ticker']} 财年："
        f"{report['selected_fiscal_years']}"
    )

    return json.dumps(
        report,
        ensure_ascii=False,
        allow_nan=False,
    )

research_agent = Agent(
    name="Financial Research Assistant",
    model="gpt-4.1-mini",
    instructions=(
        "你是金融数据研究助手，使用中文回答。"

        "当前仅支持 MSFT 和 AAPL 的年度收入及盈利能力查询。"
        "查询营业收入和收入同比时，使用 fetch_annual_revenue。"
        "查询净利润、净利率或盈利能力时，使用 fetch_profitability。"
        "若同时要求收入同比和盈利能力，两种工具都需要调用。"

        "查询已支持公司的收入时，先调用收入工具。"
        "用户要求最近 N 年时，将 N 作为 years 参数；"
        "未指定年数时默认查询三年。"
        "years 只支持 1 到 10；超出范围时说明限制，请用户调整。"
        "同一公司、相同年数的同一种工具通常只需调用一次。"
        "工具失败后不要重复尝试。"

        "工具返回的 rendered_table 由程序直接展示，"
        "你不要重复生成表格、换算金额或抄写数字及来源链接。"
        "最终回答只提供简短说明。"

        "只依据工具结果回答，不使用自身知识补充财务事实。"
        "数据不足仅代表当前工具及收入标签的覆盖范围，"
        "不代表公司没有更早的财报。"
        "当前工具没有收入变化原因的证据，不推断增长或下降原因。"
        "工具失败时如实说明未能获取数据，不编造结果。"
    ),
    tools=[
        fetch_annual_revenue,
        fetch_profitability,
    ],
)

def format_research_result(result) -> str:
    """有工具表格时展示表格，否则展示模型回答。"""
    tables = []

    for item in result.new_items:
        if item.type != "tool_call_output_item":
            continue

        try:
            payload = json.loads(item.output)
        except (TypeError, json.JSONDecodeError):
            continue

        if isinstance(payload, dict):
            table = payload.get("rendered_table")
            if isinstance(table, str) and table.strip():
                tables.append(table)

    if tables:
        return "\n\n".join(tables)

    return str(result.final_output)

async def run_research(question: str):
    """执行一次研究任务，返回完整运行结果。"""
    question = question.strip()
    if not question:
        raise ValueError("问题不能为空")

    for variable in ["OPENAI_API_KEY", "SEC_USER_AGENT"]:
        if not os.getenv(variable):
            raise ValueError(f"请先设置 {variable}")

    return await Runner.run(
        research_agent,
        question,
        max_turns=3,
    )

async def main():
    question = input("请输入研究问题：").strip()
    if not question:
        print("问题不能为空。")
        return

    result = await run_research(question)

    print("\n执行记录：")
    for item in result.new_items:
        print("-", item.type)

        if item.type == "tool_call_item":
            print("  工具：", item.raw_item.name)
            print("  参数：", item.raw_item.arguments)

    print("\n研究结果：")
    print(format_research_result(result))

if __name__ == "__main__":
    asyncio.run(main())
