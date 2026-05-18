"""
Geocoding API Pydantic 模型與驗證工具
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError


class AddressComponent(BaseModel):
    long_name: Optional[str] = None
    short_name: Optional[str] = None
    types: List[str] = Field(default_factory=list)


class Location(BaseModel):
    lat: float
    lng: float


class Geometry(BaseModel):
    location: Location


class PlusCode(BaseModel):
    global_code: Optional[str] = None


class GeocodingResult(BaseModel):
    place_id: Optional[str] = None
    formatted_address: str
    types: List[str] = Field(default_factory=list)
    address_components: List[AddressComponent] = Field(default_factory=list)
    geometry: Geometry
    plus_code: Optional[PlusCode] = None


class GeocodingApiResponse(BaseModel):
    status: str
    plus_code: Optional[PlusCode] = None
    results: List[GeocodingResult] = Field(default_factory=list)


def validate_geocoding_response(response: Dict[str, Any]) -> bool:
    """
    驗證 Geocoding API 下行是否符合儲存條件（SASD 附錄七）。
    """
    if not isinstance(response, dict):
        return False

    if response.get("status") != "OK":
        return False

    results = response.get("results", [])
    if not isinstance(results, list) or not results:
        return False

    try:
        parsed = GeocodingApiResponse.model_validate(response)
    except ValidationError:
        return False

    first = parsed.results[0]
    if not first.formatted_address:
        return False
    if first.geometry.location.lat is None or first.geometry.location.lng is None:
        return False
    if not first.address_components:
        return False
    return True


def extract_address_component(address_components: List[Dict[str, Any]], target_type: str) -> Optional[str]:
    """從 address_components 取出指定類型的 long_name。"""
    for component in address_components:
        types = component.get("types", []) if isinstance(component, dict) else []
        if target_type in types:
            return component.get("long_name")
    return None


def extract_global_code(response: Dict[str, Any]) -> Optional[str]:
    """取得 global_code，優先 root-level，再 fallback 到 results[0].plus_code。"""
    if not isinstance(response, dict):
        return None

    root_plus_code = response.get("plus_code", {})
    if isinstance(root_plus_code, dict):
        root_global_code = root_plus_code.get("global_code")
        if root_global_code:
            return root_global_code

    results = response.get("results", [])
    if not isinstance(results, list) or not results:
        return None

    first = results[0]
    if not isinstance(first, dict):
        return None

    result_plus_code = first.get("plus_code", {})
    if isinstance(result_plus_code, dict):
        return result_plus_code.get("global_code")

    return None
