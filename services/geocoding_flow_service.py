"""
Geocoding 流程編排服務
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from application.geocoding_batch_process_service import GeocodingBatchProcessService
from modules.config import config
from modules.exceptions import DataValidationError, GeoDataError
from utils.infra_logging import Logging, _logger
from utils.pubsub_services import PubSubService
from utils.request_context import get_current_log


class GeocodingFlowService:
    """負責協調 Geocoding 三階段批次流程。"""

    NEXT_STAGE = {
        "contact_address": "residence_address",
        "residence_address": "contract_coordinates",
        "contract_coordinates": None,
    }

    def __init__(self) -> None:
        self.core = GeocodingBatchProcessService()
        self.pubsub_service = PubSubService()
        self.log = get_current_log()

    def handle_geocoding_request(self, request_data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """處理 /geocoding 路由請求。"""
        try:
            if self._is_pubsub_message(request_data):
                payload = self._parse_pubsub_message(request_data)
            else:
                payload = request_data or {}

            result = self._handle_payload(payload)
            return result, 200

        except DataValidationError:
            return self._create_error_response("validation_error", "Invalid request payload", 400)
        except GeoDataError as e:
            return self._create_error_response("geo_error", "Geo data processing failed", e.status_code)
        except Exception as e:
            _logger.log_text(f"Error in handle_geocoding_request: {e}", severity="Error")
            return self._create_error_response("internal_error", "Internal server error", 500)

    def _handle_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        params = payload.get("processing_params", payload)
        task_type = params.get("task_type")
        batch_number = params.get("batch_number", 1)

        if task_type not in self.NEXT_STAGE:
            raise DataValidationError(f"Invalid or missing task_type: {task_type}")

        try:
            batch_number_int = int(batch_number)
        except Exception as e:
            raise DataValidationError(f"Invalid batch_number: {batch_number}") from e

        def callback_handler(context) -> Optional[str]:
            if context.is_last_batch:
                return None
            return self.pubsub_service.publish_geocoding_daily_recall(
                task_type=task_type,
                current_batch=int(context.batch_number),
            )

        result = self.core.process_stage(
            task_type=task_type,
            batch_number=batch_number_int,
            callback_handler=callback_handler,
            batch_uuid=getattr(self.log, "log_uuid", None),
        )

        # Switch to next stage only when current stage is fully completed.
        if result.get("status") == "completed":
            self._publish_next_action(task_type)

        return result

    def _publish_next_action(self, current_task_type: str) -> None:
        next_task_type = self.NEXT_STAGE[current_task_type]

        if next_task_type:
            msg_id = self.pubsub_service.publish_geocoding_stage_start(next_task_type, batch_number=1)
            if not msg_id:
                raise GeoDataError(f"Failed to publish next geocoding stage: {next_task_type}", 500)
            _logger.log_text(
                f"Geocoding stage transition published: {current_task_type} -> {next_task_type}",
                severity="Info",
            )
            return

        _logger.log_text("All geocoding stages are done", severity="Info")

        message = {"file_list": ["RAW_EDEP_DATASET.GEOCODING"]}
        message_id = self.pubsub_service.publish_pubsub_message(
            topic_name=config.anonymization_pubsub_topic,
            message=message,
            project_id=config.pubsub_project_id,
        )
        _logger.log_text(
            f"Anonymization notification published after geocoding completion: {message_id}",
            severity="Info",
        )

        # Write final flow log after all geocoding tasks are complete.
        if isinstance(self.log, Logging):
            self.log.flowlog(
                task_name="process_batch",
                task_code="01",
                message="All job completed",
                status=self.log.status_s,
                severity=self.log.severity_3,
            )

    def _is_pubsub_message(self, data: Dict[str, Any]) -> bool:
        return bool(data) and isinstance(data, dict) and "message" in data and "data" in data["message"]

    def _parse_pubsub_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            message_data = base64.b64decode(data["message"]["data"]).decode("utf-8")
            return json.loads(message_data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise DataValidationError(f"Invalid Pub/Sub message format: {str(e)}")

    def _create_error_response(
        self,
        error_type: str,
        message: str,
        status_code: int,
    ) -> Tuple[Dict[str, Any], int]:
        return {
            "status": "error",
            "error_type": error_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }, status_code
