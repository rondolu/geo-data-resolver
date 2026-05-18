"""Geocoding client 重試與致命錯誤測試。"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def _install_google_cloud_stubs() -> None:
    """安裝 Google Cloud 測試替身模組。

    Args:
        無。

    Returns:
        None: 完成測試替身注入。
    """
    logging_module = types.ModuleType("google.cloud.logging")
    logging_client = MagicMock()
    logging_client.logger.return_value = MagicMock()
    logging_module.Client = MagicMock(return_value=logging_client)

    bigquery_module = types.ModuleType("google.cloud.bigquery")
    bigquery_module.Client = MagicMock(return_value=MagicMock())
    bigquery_module.QueryJobConfig = MagicMock
    bigquery_module.ScalarQueryParameter = MagicMock

    storage_module = types.ModuleType("google.cloud.storage")
    storage_module.Client = MagicMock(return_value=MagicMock())

    sys.modules["google.cloud.logging"] = logging_module
    sys.modules["google.cloud.bigquery"] = bigquery_module
    sys.modules["google.cloud.storage"] = storage_module

    import google.cloud as cloud_pkg

    cloud_pkg.logging = logging_module
    cloud_pkg.bigquery = bigquery_module
    cloud_pkg.storage = storage_module


_install_google_cloud_stubs()


from infrastructure.google_maps_client import GoogleMapsAPIClient
from modules.exceptions import GoogleMapsAPIError


class FakeResponse:
    """用於模擬 requests 回應的簡易假物件。"""

    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.content = b"{}"

    def json(self):
        return self._payload


@patch("infrastructure.google_maps_client.SecretManagerService.get_api_key", return_value="dummy-key")
@patch("infrastructure.google_maps_client.time.sleep")
def test_unknown_error_retries_and_raises(mock_sleep, _mock_key):
    """驗證 UNKNOWN_ERROR 會重試至上限後拋出錯誤。

    Args:
        mock_sleep: time.sleep 的 patch 物件。
        _mock_key: SecretManagerService.get_api_key 的 patch 物件。

    Returns:
        None: 以呼叫次數與拋錯斷言驗證重試策略。
    """
    client = GoogleMapsAPIClient()
    client.max_retries = 3
    client.min_interval = 0
    client.session = MagicMock()
    client.session.get = MagicMock(return_value=FakeResponse(payload={"status": "UNKNOWN_ERROR"}))

    with pytest.raises(GoogleMapsAPIError):
        client.get_geocoding(address="abc")

    assert client.session.get.call_count == 4
    assert mock_sleep.call_count == 3


@patch("infrastructure.google_maps_client.SecretManagerService.get_api_key", return_value="dummy-key")
def test_request_denied_raises_immediately(_mock_key):
    """驗證 REQUEST_DENIED 發生時不重試並立即拋錯。

    Args:
        _mock_key: SecretManagerService.get_api_key 的 patch 物件。

    Returns:
        None: 以呼叫次數與拋錯斷言驗證行為。
    """
    client = GoogleMapsAPIClient()
    client.max_retries = 3
    client.session = MagicMock()
    client.session.get = MagicMock(return_value=FakeResponse(payload={"status": "REQUEST_DENIED"}))

    with pytest.raises(GoogleMapsAPIError):
        client.get_geocoding(address="abc")

    assert client.session.get.call_count == 1


@patch("infrastructure.google_maps_client.SecretManagerService.get_api_key", return_value="dummy-key")
def test_geocoding_request_always_includes_fulfill_on_zero_results(_mock_key):
    """驗證 Geocoding request 皆包含 fulfill_on_zero_results=true 參數。"""
    client = GoogleMapsAPIClient()
    client.session = MagicMock()
    client.session.get = MagicMock(return_value=FakeResponse(payload={"status": "OK", "results": []}))

    client.get_geocoding(address="abc")
    client.get_geocoding(latlng="10.1,105.7")

    first_params = client.session.get.call_args_list[0].kwargs["params"]
    second_params = client.session.get.call_args_list[1].kwargs["params"]

    assert first_params["fulfill_on_zero_results"] == "true"
    assert first_params["address"] == "abc"
    assert second_params["fulfill_on_zero_results"] == "true"
    assert second_params["latlng"] == "10.1,105.7"
