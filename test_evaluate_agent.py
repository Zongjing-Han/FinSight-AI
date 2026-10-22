import asyncio
import json
from types import SimpleNamespace

import evaluate_agent


def test_evaluate_case_records_tool_output(monkeypatch):
    tool_output = {
        "ticker": "AAPL",
        "selected_fiscal_years": [2023, 2024, 2025],
    }

    async def fake_run(agent, question, max_turns):
        return SimpleNamespace(
            new_items=[
                SimpleNamespace(
                    type="tool_call_item",
                    raw_item=SimpleNamespace(
                        name="fetch_annual_revenue",
                        arguments=json.dumps({
                            "ticker": "AAPL",
                            "years": 3,
                        }),
                    ),
                ),
                SimpleNamespace(
                    type="tool_call_output_item",
                    output=tool_output,
                ),
            ],
            final_output="模拟回答",
            context_wrapper=SimpleNamespace(
                usage=SimpleNamespace(
                    requests=2,
                    input_tokens=100,
                    output_tokens=20,
                    total_tokens=120,
                ),
            ),
        )

    # 替换真实 Runner，确保测试不会调用模型或财务工具
    monkeypatch.setattr(
        evaluate_agent.Runner,
        "run",
        fake_run,
    )

    case = {
        "id": "aapl_recent_3",
        "question": "查询苹果最近三年的收入",
        "expected_tool_calls": 1,
        "expected_ticker": "AAPL",
        "expected_years": 3,
    }

    report = asyncio.run(
        evaluate_agent.evaluate_case(case)
    )

    assert report["status"] == "completed"
    assert report["routing_passed"] is True
    assert report["tool_calls"] == [{
        "name": "fetch_annual_revenue",
        "arguments": {"ticker": "AAPL", "years": 3},
    }]
    assert report["tool_outputs"] == [{
        "output": tool_output,
    }]
    assert report["answer"] == "模拟回答"
    assert report["usage"]["total_tokens"] == 120

    # 确认评估记录能保存为标准 JSON
    json.dumps(report, allow_nan=False)