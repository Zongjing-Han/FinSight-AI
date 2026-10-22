from main import (
    calculate_revenue_growth,
    extract_annual_revenue,
    fetch_company_facts,
)


facts = fetch_company_facts("0000320193")

annual_revenue = extract_annual_revenue(
    facts,
    revenue_tag="RevenueFromContractWithCustomerExcludingAssessedTax",
    fiscal_end_month=9,
)

result = calculate_revenue_growth(annual_revenue)

print("公司：", facts["entityName"])
print(
    result[
        ["fiscal_year", "start", "end", "val", "revenue_growth_pct"]
    ].to_string(index=False, na_rep="N/A")
)