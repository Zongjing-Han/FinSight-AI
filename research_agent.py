import asyncio
import os
import json

from revenue_service import (
    get_company_revenue,
    select_recent_revenue,
)
from reporting import render_revenue_table

from agents import Agent, Runner, function_tool


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

research_agent = Agent(
    name="Financial Research Assistant",
    model="gpt-4.1-mini",
    instructions=(
        "你是金融数据研究助手，使用中文回答。"

        "当前仅支持 MSFT 和 AAPL 的年度营业收入查询。"
        "对于无关问题或不支持的公司，简短说明支持范围，不调用收入工具。"

        "查询已支持公司的收入时，先调用收入工具。"
        "用户要求最近 N 年时，将 N 作为 years 参数；"
        "未指定年数时默认查询三年。"
        "years 只支持 1 到 10；超出范围时说明限制，请用户调整。"
        "同一公司同一次查询通常只需调用一次，失败后不要重复尝试。"

        "工具返回的 rendered_table 由程序直接展示，"
        "你不要重复生成表格、换算金额或抄写数字及来源链接。"
        "最终回答只提供简短说明。"

        "只依据工具结果回答，不使用自身知识补充财务事实。"
        "数据不足仅代表当前工具及收入标签的覆盖范围，"
        "不代表公司没有更早的财报。"
        "当前工具没有收入变化原因的证据，不推断增长或下降原因。"
        "工具失败时如实说明未能获取数据，不编造结果。"
    ),
    tools=[fetch_annual_revenue],
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
