import json
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import research_agent

from research_agent import format_research_result


def test_table_replaces_model_answer():
    result = SimpleNamespace(
        new_items=[
            SimpleNamespace(
                type="tool_call_output_item",
                output=json.dumps({
                    "rendered_table": "Python 生成的表格",
                }),
            ),
        ],
        final_output="模型重复抄写的数字",
    )

    assert format_research_result(result) == "Python 生成的表格"


def test_answer_is_shown_without_table():
    result = SimpleNamespace(
        new_items=[],
        final_output="目前仅支持 MSFT 和 AAPL 的收入查询。",
    )

    assert format_research_result(result) == result.final_output


def test_run_research_delegates_to_runner(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("SEC_USER_AGENT", "Test test@example.com")
    expected = SimpleNamespace(final_output="模拟结果")
    fake_run = AsyncMock(return_value=expected)
    monkeypatch.setattr(research_agent.Runner, "run", fake_run)

    result = asyncio.run(research_agent.run_research("  查询微软收入  "))

    assert result is expected
    fake_run.assert_awaited_once_with(
        research_agent.research_agent,
        "查询微软收入",
        max_turns=3,
    )
