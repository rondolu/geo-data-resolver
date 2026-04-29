"""Geocoding 批次處理服務測試。

涵蓋批次流程控制、批次記錄處理與 API 呼叫驗證。
"""

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


from application.geocoding_batch_process_service import GeocodingBatchProcessService
from application.batch_process_service import BatchContext
from modules.exceptions import GoogleMapsAPIError


def _valid_geocoding_response():
    """建立有效的 Geocoding API 回應範例資料。

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


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_first_batch_runs_update_sql(_mock_gcs, _mock_api, _mock_bq):
    """驗證第一個批次會先執行更新 SQL 再進行處理。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證執行順序。
    """
    service = GeocodingBatchProcessService()

    with patch.object(service, "_execute_update_sql") as mock_update, \
         patch.object(service, "_load_query_data", return_value=[]) as mock_load, \
         patch.object(service, "_process_single_batch", return_value={"status": "completed"}) as mock_single:
        result = service.process_stage(task_type="contact_address", batch_number=1)

    assert result["status"] == "completed"
    mock_update.assert_called_once_with("contact_address")
    mock_load.assert_called_once_with("contact_address")
    mock_single.assert_called_once()


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_non_first_batch_runs_update_sql(_mock_gcs, _mock_api, _mock_bq):
    """驗證非第一個批次同樣會先執行更新 SQL 再進行處理。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證非第一批也會執行更新 SQL。
    """
    service = GeocodingBatchProcessService()

    with patch.object(service, "_execute_update_sql") as mock_update, \
         patch.object(service, "_load_query_data", return_value=[]) as mock_load, \
         patch.object(service, "_process_single_batch", return_value={"status": "completed"}) as mock_single:
        service.process_stage(task_type="contact_address", batch_number=2)

    mock_update.assert_called_once_with("contact_address")
    mock_load.assert_called_once_with("contact_address")
    mock_single.assert_called_once()


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_unknown_error_raises_in_batch_records(_mock_gcs, _mock_api, _mock_bq):
    """驗證批次記錄遇到 UNKNOWN_ERROR 時會拋出例外。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以 pytest.raises 驗證例外拋出。
    """
    service = GeocodingBatchProcessService()
    context = BatchContext(batch_number=1, is_last_batch=True)

    with patch.object(service, "_call_geocoding_api", side_effect=GoogleMapsAPIError("UNKNOWN_ERROR", 500)):
        with pytest.raises(GoogleMapsAPIError):
            service._process_batch_records("contact_address", [{"request_address": "abc"}], context)


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_request_denied_raises_in_first_record(_mock_gcs, _mock_api, _mock_bq):
    """驗證批次記錄遇到 REQUEST_DENIED 時會拋出例外。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以 pytest.raises 驗證例外拋出。
    """
    service = GeocodingBatchProcessService()
    context = BatchContext(batch_number=1, is_last_batch=True)

    with patch.object(service, "_call_geocoding_api", side_effect=GoogleMapsAPIError("REQUEST_DENIED", 403)):
        with pytest.raises(GoogleMapsAPIError):
            service._process_batch_records("contact_address", [{"request_address": "abc"}], context)


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_non_fatal_error_continues_to_next_record(_mock_gcs, _mock_api, _mock_bq):
    """驗證非致命錯誤發生後會繼續處理下一筆記錄。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證錯誤計數與成功計數符合預期。
    """
    service = GeocodingBatchProcessService()
    context = BatchContext(batch_number=1, is_last_batch=True)

    with patch.object(
        service,
        "_call_geocoding_api",
        side_effect=[GoogleMapsAPIError("QUOTA_EXCEEDED", 429), _valid_geocoding_response()],
    ), patch.object(service, "_upload_success_rows_to_gcs"), patch.object(service, "_insert_rows_to_bq"):
        result, _ = service._process_batch_records(
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
def test_zero_results_skips_without_raising(_mock_gcs, _mock_api, _mock_bq):
    """驗證 ZERO_RESULTS 回應會寫入 BQ 且不拋出例外。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以斷言驗證 success 計數與寫入內容符合預期。
    """
    service = GeocodingBatchProcessService()
    context = BatchContext(batch_number=1, is_last_batch=True)

    with patch.object(service, "_call_geocoding_api", return_value={"status": "ZERO_RESULTS"}), \
         patch.object(service, "_upload_success_rows_to_gcs") as mock_upload, \
         patch.object(service, "_insert_rows_to_bq") as mock_insert:
        result, _ = service._process_batch_records(
            "contact_address",
            [{
                "cuid": "c1",
                "serial_number": "s1",
                "created_at": "2026-01-01",
                "partition_date": "2026-01-01",
                "request_address": "none",
            }],
            context,
        )

    assert result.skipped_count == 0
    assert result.error_count == 0
    assert result.success_count == 1
    mock_insert.assert_called_once()
    inserted_rows = mock_insert.call_args[0][0]
    assert len(inserted_rows) == 1
    assert inserted_rows[0]["REQUEST_ADDRESS"] == "none"
    assert inserted_rows[0]["PARTITION_DATE"] == "2026-01-02"
    assert inserted_rows[0]["RESPONSE_ADDRESS"] is None
    assert inserted_rows[0]["RESPONSE_PLACE_ID"] is None
    mock_upload.assert_called_once()


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_call_geocoding_api_raises_for_empty_address(_mock_gcs, _mock_api, _mock_bq):
    """驗證空白的 request_address 欄位會拋出 ValueError。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以 pytest.raises 驗證值錯誤拋出。
    """
    service = GeocodingBatchProcessService()

    with pytest.raises(ValueError, match="Missing request_address"):
        service._call_geocoding_api(
            "contact_address",
            {"request_address": "   "},
        )


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_call_geocoding_api_raises_for_missing_contract_coordinates(_mock_gcs, _mock_api, _mock_bq):
    """驗證缺少座標資訊的合約座標任務會拋出 ValueError。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以 pytest.raises 驗證值錯誤拋出。
    """
    service = GeocodingBatchProcessService()

    with pytest.raises(ValueError, match="Missing latitude/longitude"):
        service._call_geocoding_api(
            "contract_coordinates",
            {"request_latitude": None, "request_longitude": None},
        )


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_call_geocoding_api_invalid_coordinates_bubble_up_api_error(_mock_gcs, _mock_api, _mock_bq):
    """驗證無效座標 payload 會將 API 錯誤往上傳遞。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以例外斷言驗證錯誤可正確向上拋出。
    """
    service = GeocodingBatchProcessService()
    service.api_service.get_geocoding_result.side_effect = GoogleMapsAPIError("INVALID_REQUEST", 400)

    with pytest.raises(GoogleMapsAPIError, match="INVALID_REQUEST"):
        service._call_geocoding_api(
            "contract_coordinates",
            {"request_latitude": "999.9999", "request_longitude": "500.0000"},
        )

    service.api_service.get_geocoding_result.assert_called_once_with(latlng="999.9999,500.0000")


@patch("application.geocoding_batch_process_service.BigQueryService")
@patch("application.geocoding_batch_process_service.GoogleMapsAPIService")
@patch("application.geocoding_batch_process_service.GCSService")
def test_call_geocoding_api_very_long_address_bubble_up_api_error(_mock_gcs, _mock_api, _mock_bq):
    """驗證超長地址 payload 會將 API 錯誤往上傳遞。

    Args:
        _mock_gcs: GCSService 的 patch 類別物件。
        _mock_api: GoogleMapsAPIService 的 patch 類別物件。
        _mock_bq: BigQueryService 的 patch 類別物件。

    Returns:
        None: 以例外斷言驗證錯誤可正確向上拋出。
    """
    service = GeocodingBatchProcessService()
    long_address = "A" * 5000
    service.api_service.get_geocoding_result.side_effect = GoogleMapsAPIError("INVALID_REQUEST", 400)

    with pytest.raises(GoogleMapsAPIError, match="INVALID_REQUEST"):
        service._call_geocoding_api(
            "contact_address",
            {"request_address": long_address},
        )

    service.api_service.get_geocoding_result.assert_called_once_with(address=long_address)

