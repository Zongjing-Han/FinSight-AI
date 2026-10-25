import json

import pytest

import revenue_service


def test_profitability_service_preserves_sources(monkeypatch):
    def concept(value, accession):
        return {
            "units": {
                "USD": [{
                    "start": "2023-07-01",
                    "end": "2024-06-30",
                    "val": value,
                    "form": "10-K",
                    "filed": "2024-07-30",
                    "accn": accession,
                }]
            }
        }

    revenue_tag = revenue_service.COMPANY_CONFIGS["MSFT"][
        "revenue_tag"
    ]

    facts = {
        "cik": 789019,
        "entityName": "Test Company",
        "facts": {
            "us-gaap": {
                revenue_tag: concept(100, "revenue-filing"),
                "NetIncomeLoss": concept(-20, "profit-filing"),
            }
        },
    }

    monkeypatch.setattr(
        revenue_service,
        "fetch_company_facts",
        lambda cik: facts,
    )

    report = revenue_service.get_company_profitability("msft")
    row = report["annual_profitability"][0]

    assert report["ticker"] == "MSFT"
    assert row["start"] == "2023-07-01"
    assert row["end"] == "2024-06-30"
    assert row["revenue"] == 100
    assert row["net_income"] == -20
    assert row["net_margin_pct"] == pytest.approx(-20.0)
    assert row["period_match"] == "both"

    assert row["revenue_source_url"].endswith(
        "/revenuefiling/"
    )
    assert row["net_income_source_url"].endswith(
        "/profitfiling/"
    )

    json.dumps(report, allow_nan=False)