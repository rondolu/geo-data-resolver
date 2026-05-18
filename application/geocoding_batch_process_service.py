"""
Geocoding 批次處理服務

依 task_type 執行：
- 先跑更新 SQL（batch 1）
- 再跑查詢 SQL
- 逐筆呼叫 Geocoding API
- 成功資料批次寫入 GCS 與 BigQuery
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from application.batch_process_service import BatchContext, ProcessingResult
from application.bigquery_service import BigQueryService
from models.geocoding_models import (
    extract_address_component,
    extract_global_code,
    validate_geocoding_response,
)
from modules.config import config
from modules.exceptions import GoogleMapsAPIError, GeoDataError
from services.google_maps_api_service import GoogleMapsAPIService
from utils.gcs_services import GCSService
from utils.infra_logging import Logging, _logger
from utils.request_context import get_current_log


class GeocodingBatchProcessService:
    """Geocoding 批次處理核心。"""

    STAGE_SQL: Dict[str, Dict[str, str]] = {
        "contact_address": {
            "update": "geocoding_update_contact_address.sql",
            "query": "test_geocoding_query_contact_address.sql",
            "geo_type": "CONTACT_ADDRESS",
        },
        "residence_address": {
            "update": "geocoding_update_residence_address.sql",
            "query": "test_geocoding_query_residence_address.sql",
            "geo_type": "RESIDENCE_ADDRESS",
        },
        "contract_coordinates": {
            "update": "geocoding_update_contract_coordinates.sql",
            "query": "test_geocoding_query_contract_coordinates.sql",
            "geo_type": "CONTRACT_COORDINATES",
        },
    }

    def __init__(self) -> None:
        self.bq = BigQueryService()
        self.api_service = GoogleMapsAPIService()
        self.gcs = GCSService()
        self.config = config
        self.batch_size = self.config.google_maps_batch_size

        shared_log = get_current_log()
        self.log = shared_log if isinstance(shared_log, Logging) else Logging(
            mission_name="geocoding_batch_process_service",
            log_uuid=str(uuid4()),
            flow_code="E06_geo_data_resolver",
        )

    @Logging.logtobq(task_code="31")
    def process_stage(
        self,
        task_type: str,
        batch_number: int,
        callback_handler: Optional[Callable] = None,
        batch_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        if task_type not in self.STAGE_SQL:
            raise ValueError(f"Unsupported task_type: {task_type}")

        context = BatchContext(
            batch_number=batch_number,
            callback_handler=callback_handler,
            source=f"geocoding_{task_type}",
            batch_uuid=batch_uuid or getattr(self.log, "log_uuid", str(uuid4())),
        )

        # 每個批次都先跑更新 SQL
        self._execute_update_sql(task_type)

        data = self._load_query_data(task_type)
        if not data:
            context.is_last_batch = True

        return self._process_single_batch(task_type, data, context)

    def _sql_path(self, filename: str) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "sql", filename)

    @Logging.logtobq(task_code="32")
    def _execute_update_sql(self, task_type: str) -> None:
        try:
            sql_file = self.STAGE_SQL[task_type]["update"]
            sql = open(self._sql_path(sql_file), "r", encoding="utf-8").read()
            self.bq.query(sql)
            _logger.log_text(f"Query SQL executed successfully: {sql_file}", severity="Info")
        except Exception as e:
            _logger.log_text(
                f"Failed to execute geocoding update SQL | task_type={task_type} | error={e}",
                severity="Warning",
            )

    def _load_query_data(self, task_type: str) -> List[Dict[str, Any]]:
        try:
            sql_file = self.STAGE_SQL[task_type]["query"]
            sql = open(self._sql_path(sql_file), "r", encoding="utf-8").read()
            _logger.log_text(f"Query SQL executed successfully: {sql_file}", severity="Info")
            return self.bq.query(sql)
        except Exception as e:
            _logger.log_text(f"Failed to load geocoding query data: {e}", severity="Warning")
            return []

    @Logging.logtobq(task_code="33")
    def _process_single_batch(
        self,
        task_type: str,
        data: List[Dict[str, Any]],
        context: BatchContext,
    ) -> Dict[str, Any]:
        total_records = len(data)
        is_last_batch = self.batch_size > total_records
        context.is_last_batch = is_last_batch

        batch_result, pubsub_message_id = self._process_batch_records(task_type, data, context)

        payload = {
            "status": "completed" if is_last_batch else "processing",
            "task_type": task_type,
            "batch_number": context.batch_number,
            "total_records": total_records,
            "the_batch_result": {
                "success_count": batch_result.success_count,
                "error_count": batch_result.error_count,
                "skipped_count": batch_result.skipped_count,
                "processed_references": batch_result.processed_references,
            },
        }
        if pubsub_message_id:
            payload["pubsub_message_id"] = pubsub_message_id
        return payload

    @Logging.logtobq(task_code="34")
    def _process_batch_records(
        self,
        task_type: str,
        data: List[Dict[str, Any]],
        context: BatchContext,
    ) -> Tuple[ProcessingResult, Optional[str]]:
        result = ProcessingResult()
        bq_rows: List[Dict[str, Any]] = []
        gcs_rows: List[Dict[str, Any]] = []

        for record in data:
            try:
                api_response = self._call_geocoding_api(task_type, record)
                status = api_response.get("status")

                if status == "ZERO_RESULTS":
                    bq_rows.append(self._build_bq_row(task_type, record, {}))
                    gcs_rows.append(
                        {
                            "serial_number": record.get("serial_number"),
                            "payload": api_response,
                        }
                    )
                    result.success_count += 1
                    continue

                if not validate_geocoding_response(api_response):
                    result.skipped_count += 1
                    continue

                geocoding_first_result = api_response["results"][0]
                bq_rows.append(self._build_bq_row(task_type, record, geocoding_first_result, api_response))
                gcs_rows.append(
                    {
                        "serial_number": record.get("serial_number"),
                        "payload": api_response,
                    }
                )
                result.success_count += 1

            except GoogleMapsAPIError as e:
                # REQUEST_DENIED 與 UNKNOWN_ERROR 必須終止流程
                error_message = str(e)
                if "REQUEST_DENIED" in error_message or "UNKNOWN_ERROR" in error_message:
                    _logger.log_text(f"Fatal geocoding error: {error_message}", severity="Error")
                    raise

                result.error_count += 1
                _logger.log_text(f"Geocoding API error (record skipped): {error_message}", severity="Warning")

            except Exception as e:
                result.error_count += 1
                _logger.log_text(f"Unexpected record processing error: {e}", severity="Warning")

        self._upload_success_rows_to_gcs(gcs_rows)
        self._insert_rows_to_bq(bq_rows)

        pubsub_message_id = None
        if context.callback_handler and not context.is_last_batch:
            pubsub_message_id = context.callback_handler(context)

        return result, pubsub_message_id

    def _call_geocoding_api(self, task_type: str, record: Dict[str, Any]) -> Dict[str, Any]:
        if task_type == "contract_coordinates":
            lat = record.get("request_latitude")
            lng = record.get("request_longitude")
            if lat is None or lng is None:
                raise ValueError("Missing latitude/longitude for contract_coordinates")

            lat_str = lat.strip()
            lng_str = lng.strip()
            latlng = f"{lat_str},{lng_str}"
            
            return self.api_service.get_geocoding_result(latlng=latlng)

        address = record.get("request_address")
        if not address or str(address).strip() == "":
            raise ValueError("Missing request_address for address geocoding")

        return self.api_service.get_geocoding_result(address=str(address))

    def _build_bq_row(
        self,
        task_type: str,
        source_record: Dict[str, Any],
        geocoding_first_result: Dict[str, Any],
        api_full_response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        bq_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")
        source_partition_date = source_record["partition_date"]
        target_partition_date = (source_partition_date + timedelta(days=1)).strftime("%Y-%m-%d")

        geometry = geocoding_first_result.get("geometry", {})
        location = geometry.get("location", {}) if isinstance(geometry, dict) else {}
        components = geocoding_first_result.get("address_components", []) if isinstance(geocoding_first_result, dict) else []
        place_types = geocoding_first_result.get("types", []) if isinstance(geocoding_first_result, dict) else []
        response_payload = api_full_response if isinstance(api_full_response, dict) else geocoding_first_result
        global_code = extract_global_code(response_payload)

        request_longitude = source_record.get("request_longitude") if task_type == "contract_coordinates" else None
        request_latitude = source_record.get("request_latitude") if task_type == "contract_coordinates" else None
        request_address = source_record.get("request_address") if task_type != "contract_coordinates" else None

        return {
            "PARTITION_DATE": target_partition_date,
            "CUID": source_record.get("cuid"),
            "SERIAL_NUMBER": source_record.get("serial_number"),
            "CREATED_AT": source_record.get("created_at"),
            "GEO_TYPE": self.STAGE_SQL[task_type]["geo_type"],
            "REQUEST_LONGITUDE": request_longitude,
            "REQUEST_LATITUDE": request_latitude,
            "REQUEST_ADDRESS": request_address,
            "RESPONSE_PLACE_ID": geocoding_first_result.get("place_id"),
            "RESPONSE_ADDRESS": geocoding_first_result.get("formatted_address"),
            "RESPONSE_GLOBAL_CODE": global_code,
            "RESPONSE_PLACE_TYPES": ",".join(place_types) if isinstance(place_types, list) and place_types else None,
            "RESPONSE_LONGITUDE": str(location.get("lng")) if location.get("lng") is not None else None,
            "RESPONSE_LATITUDE": str(location.get("lat")) if location.get("lat") is not None else None,
            "RESPONSE_COUNTRY": extract_address_component(components, "country"),
            "RESPONSE_CITY": extract_address_component(components, "administrative_area_level_1"),
            "RESPONSE_DISTRICT": extract_address_component(components, "administrative_area_level_2"),
            "RESPONSE_WARD": extract_address_component(components, "sublocality_level_1"),
            "RESPONSE_STREET": extract_address_component(components, "route"),
            "BQ_CREATED_TIME": bq_ts,
            "BQ_UPDATED_TIME": bq_ts,
        }

    def _upload_success_rows_to_gcs(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return

        bucket = self.config.gcs_bucket_name
        prefix = self.config.gcs_geocoding_blob_path
        if not bucket:
            raise RuntimeError("GCS bucket_name not configured")

        data_date = datetime.now().strftime("%Y%m%d")
        for row in rows:
            serial_number = row.get("serial_number") or "null"
            blob_name = f"{prefix}/{data_date}_{serial_number}.json"
            payload = json.dumps(row.get("payload", {}), ensure_ascii=False)
            self.gcs.upload_text(bucket, blob_name, payload, content_type="application/json")

    def _insert_rows_to_bq(self, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return

        ok = self.bq.insert_rows(rows, table_name=self.config.geocoding_table)
        if not ok:
            _logger.log_text("Insert geocoding rows to BigQuery failed", severity="Error")
