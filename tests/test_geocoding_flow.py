"""Geocoding 流程服務轉階與錯誤處理測試。"""

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


from services.geocoding_flow_service import GeocodingFlowService
from modules.exceptions import GoogleMapsAPIError


@patch("services.geocoding_flow_service.GeocodingBatchProcessService")
@patch("services.geocoding_flow_service.PubSubService")
def test_completed_contact_stage_publishes_next_stage(mock_pubsub_cls, mock_core_cls):
    """驗證 contact_address 完成後會發布下一個 stage。

    Args:
        mock_pubsub_cls: PubSubService 的 patch 類別物件。
        mock_core_cls: GeocodingBatchProcessService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證發佈參數。
    """
    mock_core = mock_core_cls.return_value
    mock_pubsub = mock_pubsub_cls.return_value

    mock_core.process_stage.return_value = {
        "status": "completed",
        "task_type": "contact_address",
        "batch_number": 1,
    }
    mock_pubsub.publish_geocoding_stage_start.return_value = "msg-1"

    service = GeocodingFlowService()
    payload = {
        "processing_params": {
            "task_type": "contact_address",
            "batch_number": 1,
        }
    }
    result, status = service.handle_geocoding_request(payload)

    assert status == 200
    assert result["status"] == "completed"
    mock_pubsub.publish_geocoding_stage_start.assert_called_once_with("residence_address", batch_number=1)


@patch("services.geocoding_flow_service.GeocodingBatchProcessService")
@patch("services.geocoding_flow_service.PubSubService")
def test_completed_final_stage_publishes_anonymization(mock_pubsub_cls, mock_core_cls):
    """驗證最終 stage 完成後會發布 anonymization 訊息。

    Args:
        mock_pubsub_cls: PubSubService 的 patch 類別物件。
        mock_core_cls: GeocodingBatchProcessService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證發佈行為。
    """
    mock_core = mock_core_cls.return_value
    mock_pubsub = mock_pubsub_cls.return_value

    mock_core.process_stage.return_value = {
        "status": "completed",
        "task_type": "contract_coordinates",
        "batch_number": 1,
    }
    mock_pubsub.publish_pubsub_message.return_value = "msg-2"

    service = GeocodingFlowService()
    payload = {
        "processing_params": {
            "task_type": "contract_coordinates",
            "batch_number": 1,
        }
    }
    result, status = service.handle_geocoding_request(payload)

    assert status == 200
    assert result["status"] == "completed"
    mock_pubsub.publish_pubsub_message.assert_called_once()


@patch("services.geocoding_flow_service.GeocodingBatchProcessService")
@patch("services.geocoding_flow_service.PubSubService")
def test_processing_contact_stage_publishes_daily_recall(mock_pubsub_cls, mock_core_cls):
    """驗證 processing 狀態下會發布 daily recall 訊息。

    Args:
        mock_pubsub_cls: PubSubService 的 patch 類別物件。
        mock_core_cls: GeocodingBatchProcessService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證 recall 訊息與狀態。
    """
    mock_core = mock_core_cls.return_value
    mock_pubsub = mock_pubsub_cls.return_value

    def _process_stage_side_effect(*args, **kwargs):
        """模擬 process_stage 在 processing 狀態下回傳 recall 訊息。

        Args:
            *args: 測試替身呼叫時傳入的位置參數。
            **kwargs: 測試替身呼叫時傳入的具名參數，需包含 callback_handler。

        Returns:
            dict: 模擬的 processing 階段回應內容。
        """
        callback_handler = kwargs["callback_handler"]
        callback_result = callback_handler(types.SimpleNamespace(is_last_batch=False, batch_number=1))
        return {
            "status": "processing",
            "task_type": "contact_address",
            "batch_number": 1,
            "pubsub_message_id": callback_result,
        }

    mock_core.process_stage.side_effect = _process_stage_side_effect
    mock_pubsub.publish_geocoding_daily_recall.return_value = "msg-recall-1"

    service = GeocodingFlowService()
    payload = {
        "processing_params": {
            "task_type": "contact_address",
            "batch_number": 1,
        }
    }
    result, status = service.handle_geocoding_request(payload)

    assert status == 200
    assert result["status"] == "processing"
    assert result["pubsub_message_id"] == "msg-recall-1"
    mock_pubsub.publish_geocoding_daily_recall.assert_called_once_with(task_type="contact_address", current_batch=1)


@patch("services.geocoding_flow_service.GeocodingBatchProcessService")
@patch("services.geocoding_flow_service.PubSubService")
def test_request_denied_returns_geo_error(mock_pubsub_cls, mock_core_cls):
    """驗證 REQUEST_DENIED 會映射為 403 的 geo_error 回應。

    Args:
        mock_pubsub_cls: PubSubService 的 patch 類別物件。
        mock_core_cls: GeocodingBatchProcessService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證錯誤類型與狀態碼。
    """
    _ = mock_pubsub_cls
    mock_core = mock_core_cls.return_value
    mock_core.process_stage.side_effect = GoogleMapsAPIError("REQUEST_DENIED", status_code=403)

    service = GeocodingFlowService()
    payload = {
        "processing_params": {
            "task_type": "contact_address",
            "batch_number": 1,
        }
    }
    result, status = service.handle_geocoding_request(payload)

    assert status == 403
    assert result["status"] == "error"
    assert result["error_type"] == "geo_error"


@patch("services.geocoding_flow_service.GeocodingBatchProcessService")
@patch("services.geocoding_flow_service.PubSubService")
def test_invalid_payload_returns_400(mock_pubsub_cls, mock_core_cls):
    """驗證缺少必要欄位的 payload 會回傳 400。

    Args:
        mock_pubsub_cls: PubSubService 的 patch 類別物件。
        mock_core_cls: GeocodingBatchProcessService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證狀態碼與錯誤狀態。
    """
    _ = mock_pubsub_cls
    _ = mock_core_cls

    service = GeocodingFlowService()
    result, status = service.handle_geocoding_request({"processing_params": {"batch_number": 1}})

    assert status == 400
    assert result["status"] == "error"
