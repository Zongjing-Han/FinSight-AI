from reporting import render_profitability_table


def test_profitability_table_formats_values_and_sources():
    report = {
        "ticker": "TEST",
        "annual_profitability": [
            {
                "fiscal_year": 2024,
                "start": "2023-07-01",
                "end": "2024-06-30",
                "revenue": 10_000_000_000,
                "net_income": -2_000_000_000,
                "net_margin_pct": -20.0,
                "revenue_source_url": "https://example.com/revenue",
                "net_income_source_url": "https://example.com/profit",
            },
        ],
    }

    table = render_profitability_table(report)

    assert "| 2024 | 100.00 | -20.00 | -20.00 |" in table
    assert "[来源](https://example.com/revenue)" in table
    assert "[来源](https://example.com/profit)" in table
    assert "归母净利润（亿美元）" in table
    assert "归属于母公司的税后净利润" in table


def test_profitability_table_preserves_missing_values():
    report = {
        "ticker": "TEST",
        "annual_profitability": [
            {
                "fiscal_year": 2024,
                "start": "2023-07-01",
                "end": "2024-06-30",
                "revenue": 10_000_000_000,
                "net_income": None,
                "net_margin_pct": None,
                "revenue_source_url": "https://example.com/revenue",
                "net_income_source_url": None,
            },
        ],
    }

    table = render_profitability_table(report)

    assert "| 2024 | 100.00 | N/A | 无法计算 |" in table
    assert "| 缺失 |" in table
    assert "N/A 表示数据缺失，不代表零" in table
    assert "(None)" not in table