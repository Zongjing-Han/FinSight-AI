import pandas as pd
import pytest
import main
import requests
import json

from main import revenue_to_records

from main import (
    calculate_revenue_growth,
    extract_msft_annual_revenue,
    extract_annual_revenue
)

from main import extract_annual_revenue

def test_revenue_growth():
    # 故意打乱年份，检查函数是否正确排序
    source = pd.DataFrame({
        "fiscal_year": [2024, 2023, 2026],
        "val": [120, 100, 180],
    })
    original = source.copy(deep=True)

    result = calculate_revenue_growth(source)

    # 输出应按年份排序
    assert result["fiscal_year"].tolist() == [2023, 2024, 2026]

    # 第一年没有上年数据
    assert pd.isna(result.loc[0, "revenue_growth_pct"])

    # 100 → 120，增长率为 20%
    assert result.loc[1, "revenue_growth_pct"] == pytest.approx(20.0)

    # 缺少 2025 年，不能把跨两年的变化当成同比
    assert pd.isna(result.loc[2, "revenue_growth_pct"])

    # 函数不应该修改传入的原始表
    pd.testing.assert_frame_equal(source, original)

def test_growth_with_zero_previous_revenue():
    source = pd.DataFrame({
        "fiscal_year": [2023, 2024],
        "val": [0, 100],
    })

    result = calculate_revenue_growth(source)

    assert pd.isna(result.loc[1, "revenue_growth_pct"])

def test_extract_annual_revenue():
    records = [
        # 原始年度记录
        {
            "start": "2022-07-01",
            "end": "2023-06-30",
            "val": 100,
            "form": "10-K",
            "filed": "2023-07-27",
            "accn": "original",
        },
        # 后续披露调整后的同一年度记录，应保留这条
        {
            "start": "2022-07-01",
            "end": "2023-06-30",
            "val": 105,
            "form": "10-K",
            "filed": "2024-07-30",
            "accn": "updated",
        },
        # 即使出现在 10-K 中，季度收入也应被排除
        {
            "start": "2023-01-01",
            "end": "2023-03-31",
            "val": 25,
            "form": "10-K",
            "filed": "2023-07-27",
            "accn": "quarter",
        },
        # 缺少金额的年度记录，应被排除
        {
            "start": "2023-07-01",
            "end": "2024-06-30",
            "form": "10-K",
            "filed": "2024-07-30",
            "accn": "missing-value",
        },
    ]

    # 模拟 SEC 数据的嵌套结构，不发送网络请求
    facts = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": records}
                }
            }
        }
    }

    result = extract_msft_annual_revenue(facts)

    assert len(result) == 1
    assert result.iloc[0]["fiscal_year"] == 2023
    assert result.iloc[0]["val"] == 105
    assert result.iloc[0]["accn"] == "updated"

@pytest.mark.parametrize(
    "start,end,end_month",
    [
        ("2022-09-25", "2023-09-30", 9),  # Apple 风格：53 周
        ("2023-07-01", "2024-06-30", 6),  # 微软风格：含闰日
    ],
)
def test_extract_annual_revenue_for_different_calendars(
    start, end, end_month
):
    tag = "RevenueFromContractWithCustomerExcludingAssessedTax"

    records = [
        {
            "start": start,
            "end": end,
            "val": 100,
            "form": "10-K",
            "filed": "2024-11-01",
            "accn": "annual",
        },
        {
            "start": "2023-07-01",
            "end": "2023-09-30",
            "val": 25,
            "form": "10-K",
            "filed": "2024-11-01",
            "accn": "quarter",
        },
    ]

    facts = {
        "facts": {
            "us-gaap": {
                tag: {"units": {"USD": records}}
            }
        }
    }

    result = extract_annual_revenue(
        facts,
        revenue_tag=tag,
        fiscal_end_month=end_month,
    )

    assert len(result) == 1
    assert result.iloc[0]["accn"] == "annual"
    assert result.iloc[0]["val"] == 100
    assert result.iloc[0]["fiscal_year"] == pd.Timestamp(end).year

def test_main_handles_timeout(monkeypatch, capsys):
    def fake_fetch(cik):
        raise requests.exceptions.Timeout("模拟超时")

    # 用模拟函数替换真实请求，并设置命令行参数
    monkeypatch.setattr(main, "fetch_company_facts", fake_fetch)
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--ticker", "MSFT"],
    )

    with pytest.raises(SystemExit) as error:
        main.main()

    assert error.value.code == 1

    captured = capsys.readouterr()
    assert "请求 SEC 超时" in captured.err

def test_main_handles_http_403(monkeypatch, capsys):
    def fake_fetch(cik):
        response = requests.Response()
        response.status_code = 403
        raise requests.exceptions.HTTPError(
            "模拟访问被拒绝",
            response=response,
        )

    monkeypatch.setattr(main, "fetch_company_facts", fake_fetch)
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--ticker", "MSFT"],
    )

    with pytest.raises(SystemExit) as error:
        main.main()

    assert error.value.code == 1
    assert "SEC 返回 HTTP 403" in capsys.readouterr().err

def test_revenue_to_records():
    source = pd.DataFrame({
        "fiscal_year": [2023, 2024],
        "val": [100, 120],
        "revenue_growth_pct": [float("nan"), 20.0],
        "source_url": [
            "https://example.com/2023",
            "https://example.com/2024",
        ],
    })

    records = revenue_to_records(source)

    assert records[0] == {
        "fiscal_year": 2023,
        "revenue": 100,
        "growth_pct": None,
        "source_url": "https://example.com/2023",
    }
    assert records[1]["growth_pct"] == pytest.approx(20.0)

    # 严格转换：如果还存在 NaN 等非标准值，立即报错
    json_text = json.dumps(records, allow_nan=False)

    # 转成 JSON 再读回来，内容应保持一致
    assert json.loads(json_text) == records