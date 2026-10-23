import json
from types import SimpleNamespace

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