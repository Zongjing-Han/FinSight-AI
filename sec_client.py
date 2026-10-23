import json
import os
import time
from pathlib import Path

import requests


DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "data" / "cache"


def fetch_company_facts(
    cik: str,
    *,
    refresh: bool = False,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    ttl_seconds: int = 3600,
) -> dict:
    """获取 Company Facts，优先使用未过期的本地缓存。"""
    if not cik.isascii() or not cik.isdigit() or len(cik) > 10:
        raise ValueError("CIK 必须是最多十位的数字字符串")
    if ttl_seconds < 0:
        raise ValueError("缓存有效期不能为负数")

    cik = cik.zfill(10)
    cache_path = Path(cache_dir) / f"CIK{cik}.json"

    # 1. 非强制刷新时，尝试读取未过期缓存
    if not refresh:
        try:
            age = time.time() - cache_path.stat().st_mtime

            if 0 <= age < ttl_seconds:
                cached = json.loads(
                    cache_path.read_text(encoding="utf-8")
                )

                if (
                    isinstance(cached, dict)
                    and str(cached.get("cik")).zfill(10) == cik
                    and isinstance(cached.get("facts"), dict)
                ):
                    return cached
        except (OSError, ValueError):
            # 缓存不存在、无法读取或 JSON 损坏时，重新请求
            pass

    # 2. 没有可用缓存，再访问 SEC
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        raise ValueError("请先设置 SEC_USER_AGENT 环境变量")

    url = (
        "https://data.sec.gov/api/xbrl/companyfacts/"
        f"CIK{cik}.json"
    )

    response = requests.get(
        url,
        headers={"User-Agent": user_agent},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    # 3. 验证基本结构，避免把错误响应写进缓存
    if (
        not isinstance(data, dict)
        or str(data.get("cik")).zfill(10) != cik
        or not isinstance(data.get("facts"), dict)
    ):
        raise ValueError("SEC 响应缺少有效的 CIK 或 facts")

    # 4. 保存成功获取的数据
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(data, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )

    return data