"""Geocoding 管線邊界情境與韌性測試。"""

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

from application.batch_process_service import BatchContext
from application.geocoding_batch_process_service import GeocodingBatchProcessService
from infrastructure.google_maps_client import GoogleMapsAPIClient
from models.geocoding_models import validate_geocoding_response
from modules.exceptions import GoogleMapsAPIError
from services.geocoding_flow_service import GeocodingFlowService
from services.google_maps_api_service import GoogleMapsAPIService
from utils.infra_logging import Logging
from utils.pubsub_services import PubSubService
from utils.request_context import clear_current_log, set_current_log


class FakeResponse:
    """用於模擬 HTTP 回應的簡易假物件。"""

    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.content = b"{}"

    def json(self):
        return self._payload


def _valid_geocoding_response():
    """建立有效的 Geocoding 回應範例資料。

    Args:
        無。

    Returns:
        dict: 可通過驗證的 Geocoding 回應結構。
    """
    return {
        "status": "OK",
        "results": [
            {
                "place_id": "pid-1",
                "formatted_address": "123 Test Street",
                "types": ["street_address"],
                "address_components": [
                    {"long_name": "Vietnam", "types": ["country"]},
                    {"long_name": "Ho Chi Minh", "types": ["administrative_area_level_1"]},
                    {"long_name": "District 10", "types": ["administrative_area_level_2"]},
                    {"long_name": "Ward 1", "types": ["sublocality_level_1"]},
                    {"long_name": "Ly Thuong Kiet", "types": ["route"]},
                ],
                "geometry": {"location": {"lat": 10.7734, "lng": 106.6669}},
                "plus_code": {"global_code": "7P28QPX7+QX"},
            }
        ],
    }


@patch("infrastructure.google_maps_client.SecretManagerService.get_api_key", return_value="dummy-key")
@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_o1_access_gcp_resources(mock_gcs, mock_api_service, mock_bq, _mock_key):
    """驗證核心服務可正常初始化並可存取 GCP 相關資源。

    Args:
        mock_gcs: GCSService 的 patch 類別物件。
        mock_api_service: GoogleMapsAPIService 的 patch 類別物件。
        mock_bq: BigQueryService 的 patch 類別物件。
        _mock_key: SecretManagerService.get_api_key 的 patch 物件。

    Returns:
        None: 以斷言驗證依賴物件初始化狀態。
    """
    svc = GeocodingBatchProcessService()
    client = GoogleMapsAPIClient()

    assert svc.bq is not None
    assert svc.gcs is not None
    assert svc.api_service is not None
    assert client.api_key == "dummy-key"
    mock_bq.assert_called()
    mock_gcs.assert_called()
    mock_api_service.assert_called()


@patch("infrastructure.google_maps_client.SecretManagerService.get_api_key", return_value="dummy-key")
@patch("infrastructure.google_maps_client.time.sleep")
def test_o2_normal_request_under_rate_limit(_mock_sleep, _mock_key):
    """驗證符合速率限制時可成功取得 Geocoding 回應。

    Args:
        _mock_sleep: time.sleep 的 patch 物件。
        _mock_key: SecretManagerService.get_api_key 的 patch 物件。

    Returns:
        None: 以斷言驗證回應狀態與重試次數。
    """
    client = GoogleMapsAPIClient()
    client.min_interval = 0
    client.session = MagicMock()
    client.session.get = MagicMock(return_value=FakeResponse(payload={"status": "OK", "results": []}))

    payload, retry_count = client.get_geocoding(address="abc")
    assert payload.get("status") == "OK"
    assert retry_count == 0


def test_o3_response_pass_pydantic():
    """驗證完整回應可通過 Pydantic 檢核。

    Args:
        無。

    Returns:
        None: 以斷言驗證模型驗證結果。
    """
    assert validate_geocoding_response(_valid_geocoding_response()) is True


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_o4_write_to_gcs_and_bq(_mock_gcs, _mock_api, _mock_bq):
    """驗證成功發查資料會寫入 GCS 與 BigQuery。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證寫入動作被呼叫。
    """
    svc = GeocodingBatchProcessService()
    context = BatchContext(batch_number=1, is_last_batch=True)

    with patch.object(svc, "_call_geocoding_api", return_value=_valid_geocoding_response()), \
         patch.object(svc, "_upload_success_rows_to_gcs") as mock_upload, \
         patch.object(svc, "_insert_rows_to_bq") as mock_insert:
        result, _ = svc._process_batch_records(
            "contact_address",
            [{"cuid": "c1", "serial_number": "s1", "created_at": "2026-01-01", "request_address": "abc"}],
            context,
        )

    assert result.success_count == 1
    assert mock_upload.call_count == 1
    assert mock_insert.call_count == 1


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_o5_pubsub_recall_success(_mock_gcs, _mock_api, _mock_bq):
    """驗證非最後批次時會成功觸發 recall callback。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證 callback 呼叫與 message id。
    """
    svc = GeocodingBatchProcessService()
    callback = MagicMock(return_value="msg-recall")
    context = BatchContext(batch_number=1, is_last_batch=False, callback_handler=callback)

    with patch.object(svc, "_call_geocoding_api", return_value=_valid_geocoding_response()), \
         patch.object(svc, "_upload_success_rows_to_gcs"), \
         patch.object(svc, "_insert_rows_to_bq"):
        _, pubsub_message_id = svc._process_batch_records(
            "contact_address",
            [{"cuid": "c1", "serial_number": "s1", "created_at": "2026-01-01", "request_address": "abc"}],
            context,
        )

    assert pubsub_message_id == "msg-recall"
    callback.assert_called_once()


@patch("utils.pubsub_services.PubSubService.publish_pubsub_message", return_value="msg-id")
def test_o6_pubsub_filter_and_correct_task_sql(mock_publish):
    """驗證 Pub/Sub category 與 task_type 路由邏輯正確。

    Args:
        mock_publish: publish_pubsub_message 的 patch 物件。

    Returns:
        None: 以斷言驗證訊息屬性與任務分派。
    """
    pubsub = PubSubService()
    pubsub.publish_geocoding_stage_start("contact_address", batch_number=1)

    _, kwargs = mock_publish.call_args
    assert kwargs["attributes"].get("category") == "geocoding"

    with patch("services.geocoding_flow_service.GeocodingBatchProcessService") as mock_core_cls, \
         patch("services.geocoding_flow_service.PubSubService"):
        mock_core = mock_core_cls.return_value
        mock_core.process_stage.return_value = {
            "status": "processing",
            "task_type": "residence_address",
            "batch_number": 2,
        }
        flow = GeocodingFlowService()
        flow.handle_geocoding_request({
            "processing_params": {"task_type": "residence_address", "batch_number": 2}
        })
        mock_core.process_stage.assert_called_once()
        assert mock_core.process_stage.call_args.kwargs["task_type"] == "residence_address"


@patch("services.geocoding_flow_service.GeocodingBatchProcessService")
@patch("services.geocoding_flow_service.PubSubService")
def test_o7_publish_anonymization_at_end(mock_pubsub_cls, mock_core_cls):
    """驗證最後階段完成後會發布 anonymization 訊息。

    Args:
        mock_pubsub_cls: PubSubService 的 patch 類別物件。
        mock_core_cls: GeocodingBatchProcessService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證發佈內容。
    """
    mock_core = mock_core_cls.return_value
    mock_pubsub = mock_pubsub_cls.return_value
    mock_core.process_stage.return_value = {
        "status": "completed",
        "task_type": "contract_coordinates",
        "batch_number": 1,
    }

    flow = GeocodingFlowService()
    flow.handle_geocoding_request({
        "processing_params": {"task_type": "contract_coordinates", "batch_number": 1}
    })

    mock_pubsub.publish_pubsub_message.assert_called_once()
    kwargs = mock_pubsub.publish_pubsub_message.call_args.kwargs
    assert kwargs["message"] == {"file_list": ["RAW_EDEP_DATASET.GEOCODING"]}


@patch("services.google_maps_api_service.GoogleMapsAPIClient")
def test_o8_each_request_writes_api_log(mock_client_cls):
    """驗證每次 Geocoding 呼叫都會寫入 api_log。

    Args:
        mock_client_cls: GoogleMapsAPIClient 的 patch 類別物件。

    Returns:
        None: 以斷言驗證 apilog 被呼叫。
    """
    mock_client = mock_client_cls.return_value
    mock_client.get_geocoding.return_value = (_valid_geocoding_response(), 0)

    svc = GoogleMapsAPIService()
    svc.log = MagicMock()
    svc.log.log_uuid = "uuid-1"

    svc.get_geocoding_result(address="abc")
    svc.log.apilog.assert_called_once()


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_x1_error_does_not_crash_pipeline(_mock_gcs, _mock_api, _mock_bq):
    """驗證單筆非致命錯誤不會中斷整體管線。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證成功與錯誤計數。
    """
    svc = GeocodingBatchProcessService()
    context = BatchContext(batch_number=1, is_last_batch=True)

    with patch.object(
        svc,
        "_call_geocoding_api",
        side_effect=[ValueError("bad-data"), _valid_geocoding_response()],
    ), patch.object(svc, "_upload_success_rows_to_gcs"), patch.object(svc, "_insert_rows_to_bq"):
        result, _ = svc._process_batch_records(
            "contact_address",
            [
                {"cuid": "c1", "serial_number": "s1", "created_at": "2026-01-01", "request_address": "bad"},
                {"cuid": "c2", "serial_number": "s2", "created_at": "2026-01-01", "request_address": "ok"},
            ],
            context,
        )

    assert result.error_count == 1
    assert result.success_count == 1


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_x2_request_error_caught(_mock_gcs, _mock_api, _mock_bq):
    """驗證請求層 API 錯誤可被接住並累計錯誤數。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證錯誤計數。
    """
    svc = GeocodingBatchProcessService()
    context = BatchContext(batch_number=1, is_last_batch=True)

    with patch.object(svc, "_call_geocoding_api", side_effect=GoogleMapsAPIError("GENERIC_ERROR", 500)), \
         patch.object(svc, "_upload_success_rows_to_gcs"), \
         patch.object(svc, "_insert_rows_to_bq"):
        result, _ = svc._process_batch_records(
            "contact_address",
            [{"cuid": "c1", "serial_number": "s1", "created_at": "2026-01-01", "request_address": "abc"}],
            context,
        )

    assert result.error_count == 1


@patch("infrastructure.google_maps_client.SecretManagerService.get_api_key", return_value="dummy-key")
@patch("infrastructure.google_maps_client.time.sleep")
def test_x3_retry_policy_executes(mock_sleep, _mock_key):
    """驗證暫時性失敗時會觸發重試並可恢復成功。

    Args:
        mock_sleep: time.sleep 的 patch 物件。
        _mock_key: SecretManagerService.get_api_key 的 patch 物件。

    Returns:
        None: 以斷言驗證重試次數與成功結果。
    """
    client = GoogleMapsAPIClient()
    client.min_interval = 0
    client.max_retries = 3
    client.session = MagicMock()
    client.session.get = MagicMock(
        side_effect=[
            FakeResponse(status_code=500, payload={"status": "UNKNOWN"}, text="server error"),
            FakeResponse(status_code=200, payload={"status": "OK", "results": []}),
        ]
    )

    payload, retry_count = client.get_geocoding(address="abc")

    assert payload.get("status") == "OK"
    assert retry_count == 1
    assert client.session.get.call_count == 2
    assert mock_sleep.call_count >= 1


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_x4_failed_request_written_to_flow_log(_mock_gcs, _mock_api, _mock_bq):
    """驗證無效任務輸入造成失敗時會寫入 flow_log。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證 flowlog 被呼叫。
    """
    svc = GeocodingBatchProcessService()

    shared_log = Logging(mission_name="test", log_uuid="uuid-1", flow_code="E06_geo_data_resolver")
    shared_log.flowlog = MagicMock()
    set_current_log(shared_log)

    try:
        with pytest.raises(ValueError):
            svc.process_stage(task_type="invalid_task", batch_number=1)
    finally:
        clear_current_log()

    assert shared_log.flowlog.called


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_x5_no_recall_on_last_batch_to_avoid_loop(_mock_gcs, _mock_api, _mock_bq):
    """驗證最後批次不會觸發 recall 以避免無限迴圈。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證 callback 不會被呼叫。
    """
    svc = GeocodingBatchProcessService()
    callback = MagicMock(return_value="should-not-happen")
    context = BatchContext(batch_number=1, is_last_batch=True, callback_handler=callback)

    with patch.object(svc, "_call_geocoding_api", return_value=_valid_geocoding_response()), \
         patch.object(svc, "_upload_success_rows_to_gcs"), \
         patch.object(svc, "_insert_rows_to_bq"):
        _, pubsub_message_id = svc._process_batch_records(
            "contact_address",
            [{"cuid": "c1", "serial_number": "s1", "created_at": "2026-01-01", "request_address": "abc"}],
            context,
        )

    assert pubsub_message_id is None
    callback.assert_not_called()
