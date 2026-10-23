import os

import requests

def fetch_company_facts(cik: str) -> dict:
    """从 SEC 获取指定公司的 Company Facts 数据。"""
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        raise ValueError("请先设置 SEC_USER_AGENT 环境变量")

    url = (
        "https://data.sec.gov/api/xbrl/companyfacts/"
        f"CIK{cik.zfill(10)}.json"
    )

    response = requests.get(
        url,
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    response.raise_for_status()

    return response.json()