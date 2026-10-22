import asyncio
import os

from agents import Agent, Runner, function_tool

from main import get_company_revenue, select_recent_revenue


@function_tool
def fetch_annual_revenue(ticker: str, years: int = 3) -> dict:
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

    return result

research_agent = Agent(
    name="Financial Research Assistant",
    model="gpt-4.1-mini",
    instructions=(
        "你是金融数据研究助手，使用中文回答。"
        "回答公司营业收入相关问题前，必须调用收入工具。"
        "只使用工具返回的财务数字，不编造数据。"
        "明确注明财年、金额单位和同比增长率。"
        "缺失同比应说明无法计算，不得当作零。"
        "附上对应的来源链接，并说明链接指向申报目录。"
        "当前只支持 MSFT 和 AAPL；其他公司应说明暂不支持。"
        "当前工具只提供收入数据，不据此推断收入变化的原因。"
        "用户要求最近 N 年时，将 N 作为 years 参数调用收入工具。"
        "以工具返回的 selected_fiscal_years 为准，不根据自身知识判断最新年份。"
        "展示所有返回的年度记录；若 returned_years 少于 requested_years，说明数据不足。"
        "同一公司同一次查询通常只需调用一次；失败时不得无休止重试。"
        "表格统一使用营业收入（亿美元），金额保留两位小数，"
        "单元格只填写数字；同比增长率（%）保留两位小数。"
    ),
    tools=[fetch_annual_revenue],
)

async def main():
    for variable in ["OPENAI_API_KEY", "SEC_USER_AGENT"]:
        if not os.getenv(variable):
            raise ValueError(f"请先设置 {variable}")

    question = input("请输入研究问题：").strip()
    if not question:
        print("问题不能为空。")
        return

    result = await Runner.run(
        research_agent,
        question,
        max_turns=3,
    )

    print("\n执行记录：")
    for item in result.new_items:
        print("-", item.type)

        if item.type == "tool_call_item":
            print("  工具：", item.raw_item.name)
            print("  参数：", item.raw_item.arguments)

    print("\n最终回答：")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())