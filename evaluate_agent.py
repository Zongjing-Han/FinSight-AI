import asyncio
import json
import os
import time
import argparse
from pathlib import Path

from agents import Runner

from research_agent import (
    research_agent,
    format_research_result,
)


ROOT = Path(__file__).resolve().parent


async def evaluate_case(case: dict) -> dict:
    started = time.perf_counter()

    try:
        result = await Runner.run(
            research_agent,
            case["question"],
            max_turns=3,
        )

        calls = []
        tool_outputs = []
        for item in result.new_items:
            if item.type == "tool_call_item":
                calls.append({
                    "name": item.raw_item.name,
                    "arguments": json.loads(
                        item.raw_item.arguments
                    ),
                })
            elif item.type == "tool_call_output_item":
                tool_outputs.append({
                    "output": item.output,
                })  

        checks = {
            "tool_call_count": (
                len(calls) == case["expected_tool_calls"]
            ),
        }

        if "expected_ticker" in case:
            checks["tool_and_arguments"] = (
                len(calls) == 1
                and calls[0]["name"] == case.get(
                    "expected_tool", "fetch_annual_revenue"
                )
                and calls[0]["arguments"].get("ticker")
                == case["expected_ticker"]
                and calls[0]["arguments"].get("years")
                == case["expected_years"]
            )

        usage = result.context_wrapper.usage

        return {
            "id": case["id"],
            "question": case["question"],
            "status": "completed",
            "checks": checks,
            "routing_passed": all(checks.values()),
            "tool_calls": calls,
            "tool_outputs": tool_outputs,
            "answer": result.final_output,
            "displayed_answer": format_research_result(result),
            "elapsed_seconds": round(
                time.perf_counter() - started, 3
            ),
            "usage": {
                "requests": usage.requests,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            },
        }

    except Exception as error:
        # 单条失败仍继续评估其他问题，并记录失败原因
        return {
            "id": case["id"],
            "question": case["question"],
            "status": "error",
            "routing_passed": False,
            "error_type": type(error).__name__,
            "error": str(error),
            "elapsed_seconds": round(
                time.perf_counter() - started, 3
            ),
        }


async def main():

    parser = argparse.ArgumentParser(
        description="运行 Agent 评估"
    )
    parser.add_argument(
        "--case",
        dest="case_id",
        help="只运行指定 ID 的用例；不传则运行全部",
    )
    args = parser.parse_args()

    for variable in ["OPENAI_API_KEY", "SEC_USER_AGENT"]:
        if not os.getenv(variable):
            raise ValueError(f"请先设置 {variable}")

    cases = json.loads(
        (ROOT / "eval_cases.json").read_text(encoding="utf-8")
    )
    if args.case_id:
        cases = [
            case
            for case in cases
            if case["id"] == args.case_id
        ]

        if not cases:
            parser.error(f"找不到用例：{args.case_id}")
    if not cases:
        raise ValueError("评估集不能为空")

    reports = []

    # 顺序执行，方便观察结果并控制请求并发
    for case in cases:
        print(f"\n评估：{case['id']}")
        report = await evaluate_case(case)
        reports.append(report)

        print(
            "工具路由检查：",
            "通过" if report["routing_passed"] else "未通过",
        )
        if report["status"] == "error":
            print("错误类型：", report["error_type"])

    output_dir = ROOT / "data"
    output_dir.mkdir(exist_ok=True)
    filename = (
        f"agent_eval_{cases[0]['id']}.json"
        if args.case_id
        else "agent_eval_results.json"
    )
    output_path = output_dir / filename

    output_path.write_text(
        json.dumps(
            reports,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    passed = sum(r["routing_passed"] for r in reports)
    print(f"\n工具路由通过：{passed}/{len(reports)}")
    print(f"详细结果：{output_path}")


if __name__ == "__main__":
    asyncio.run(main())
