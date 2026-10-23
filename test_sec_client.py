import json
import os

import sec_client


CIK = "0000789019"


def mock_sec(monkeypatch):
    """模拟 SEC 请求，记录调用次数。"""
    calls = []

    def fake_get(url, headers, timeout):
        calls.append(url)

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "cik": 789019,
                    "entityName": "Test Company",
                    "facts": {},
                }

        return FakeResponse()

    monkeypatch.setenv(
        "SEC_USER_AGENT",
        "FinSight-Test test@example.com",
    )
    monkeypatch.setattr(sec_client.requests, "get", fake_get)

    return calls


def test_first_request_saves_cache(monkeypatch, tmp_path):
    calls = mock_sec(monkeypatch)

    result = sec_client.fetch_company_facts(
        CIK,
        cache_dir=tmp_path,
    )

    cache_file = tmp_path / f"CIK{CIK}.json"

    assert len(calls) == 1
    assert cache_file.exists()
    assert json.loads(
        cache_file.read_text(encoding="utf-8")
    ) == result


def test_fresh_cache_skips_request(monkeypatch, tmp_path):
    calls = mock_sec(monkeypatch)

    first = sec_client.fetch_company_facts(
        CIK,
        cache_dir=tmp_path,
    )
    second = sec_client.fetch_company_facts(
        CIK,
        cache_dir=tmp_path,
    )

    assert first == second
    assert len(calls) == 1


def test_expired_cache_requests_again(monkeypatch, tmp_path):
    calls = mock_sec(monkeypatch)

    sec_client.fetch_company_facts(CIK, cache_dir=tmp_path)

    cache_file = tmp_path / f"CIK{CIK}.json"

    # 固定时钟并把缓存设为两小时前，无需真的等待
    now = 2_000_000_000
    monkeypatch.setattr(sec_client.time, "time", lambda: now)
    os.utime(cache_file, (now - 7200, now - 7200))

    sec_client.fetch_company_facts(
        CIK,
        cache_dir=tmp_path,
        ttl_seconds=3600,
    )

    assert len(calls) == 2

def test_refresh_ignores_fresh_cache(monkeypatch, tmp_path):
    calls = mock_sec(monkeypatch)

    sec_client.fetch_company_facts(CIK, cache_dir=tmp_path)

    sec_client.fetch_company_facts(
        CIK,
        cache_dir=tmp_path,
        refresh=True,
    )

    assert len(calls) == 2


def test_corrupted_cache_is_replaced(monkeypatch, tmp_path):
    calls = mock_sec(monkeypatch)

    cache_file = tmp_path / f"CIK{CIK}.json"
    cache_file.write_text(
        "{broken json",
        encoding="utf-8",
    )

    result = sec_client.fetch_company_facts(
        CIK,
        cache_dir=tmp_path,
    )

    assert len(calls) == 1
    assert json.loads(
        cache_file.read_text(encoding="utf-8")
    ) == result