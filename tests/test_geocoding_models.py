"""Geocoding 模型驗證與欄位擷取測試。"""

from models.geocoding_models import (
    extract_address_component,
    extract_global_code,
    validate_geocoding_response,
)


def test_validate_geocoding_response_success():
    """驗證完整 Geocoding 回應可通過檢核。

    Args:
        無。

    Returns:
        None: 以斷言驗證函式回傳 True。
    """
    payload = {
        "status": "OK",
        "results": [
            {
                "formatted_address": "123 Test St",
                "place_id": "pid",
                "types": ["street_address"],
                "address_components": [
                    {"long_name": "Vietnam", "types": ["country"]},
                ],
                "geometry": {
                    "location": {"lat": 10.1234, "lng": 106.1234},
                },
            }
        ],
    }
    assert validate_geocoding_response(payload) is True


def test_validate_geocoding_response_missing_fields():
    """驗證缺少必要欄位時 Geocoding 回應檢核會失敗。

    Args:
        無。

    Returns:
        None: 以斷言驗證函式回傳 False。
    """
    payload = {
        "status": "OK",
        "results": [
            {
                "formatted_address": "",
                "address_components": [],
                "geometry": {"location": {"lat": None, "lng": None}},
            }
        ],
    }
    assert validate_geocoding_response(payload) is False


def test_extract_address_component():
    """驗證地址元件擷取可正確命中與回傳缺失類型。

    Args:
        無。

    Returns:
        None: 以斷言驗證擷取結果。
    """
    components = [
        {"long_name": "Ho Chi Minh", "types": ["administrative_area_level_1"]},
        {"long_name": "Vietnam", "types": ["country"]},
    ]
    assert extract_address_component(components, "country") == "Vietnam"
    assert extract_address_component(components, "route") is None


def test_extract_global_code_prefers_root_level():
    """驗證 global_code 會優先使用 root-level plus_code。"""
    payload = {
        "plus_code": {"global_code": "ROOT-CODE"},
        "results": [{"plus_code": {"global_code": "RESULT-CODE"}}],
    }
    assert extract_global_code(payload) == "ROOT-CODE"


def test_extract_global_code_fallback_to_first_result():
    """驗證 root-level 無值時會回退到 results[0].plus_code.global_code。"""
    payload = {
        "plus_code": {},
        "results": [{"plus_code": {"global_code": "RESULT-CODE"}}],
    }
    assert extract_global_code(payload) == "RESULT-CODE"


def test_extract_global_code_returns_none_when_missing_everywhere():
    """驗證 root-level 與 result-level 都無值時回傳 None。"""
    payload = {"status": "OK", "results": []}
    assert extract_global_code(payload) is None
