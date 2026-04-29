"""Geocoding 路由層測試。"""

import base64
import json
import sys
import types
from unittest.mock import MagicMock, patch


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

from main import create_app


@patch("blueprints.geo_routes.GeocodingFlowService")
def test_pubsub_success_returns_204(mock_service_cls):
    """驗證 Pub/Sub 格式請求成功時回傳 HTTP 204。

    Args:
        mock_service_cls: GeocodingFlowService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證狀態碼。
    """
    mock_service = mock_service_cls.return_value
    mock_service.handle_geocoding_request.return_value = ({"status": "completed"}, 200)

    payload = {
        "processing_params": {
            "task_type": "contact_address",
            "batch_number": 1,
        }
    }
    message = {
        "message": {
            "data": base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        }
    }

    app = create_app()
    client = app.test_client()
    resp = client.post("/geocoding", json=message)

    assert resp.status_code == 204


@patch("blueprints.geo_routes.GeocodingFlowService")
def test_non_pubsub_returns_json(mock_service_cls):
    """驗證一般 HTTP 請求會回傳 JSON 內容。

    Args:
        mock_service_cls: GeocodingFlowService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證狀態碼與回傳內容。
    """
    mock_service = mock_service_cls.return_value
    mock_service.handle_geocoding_request.return_value = ({"status": "completed"}, 200)

    app = create_app()
    client = app.test_client()
    resp = client.post("/geocoding", json={"task_type": "contact_address", "batch_number": 1})

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"
