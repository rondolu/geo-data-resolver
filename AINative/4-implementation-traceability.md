# 4) Implementation Traceability

本文件維護需求、規格、程式與測試對照，便於變更影響分析。

## 4.1 BR -> Spec -> 程式 對照

| BR | Spec | 主要程式 |
| --- | --- | --- |
| BR-01 觸發模式 | Spec-01, Spec-02, Spec-03 | `blueprints/geo_routes.py`, `services/dataflow_service.py` |
| BR-02 載入與去重 | Spec-04, Spec-05 | `sql/get_geo_query_data.sql`, `sql/get_geo_query_data_range.sql`, `application/batch_process_service.py` |
| BR-03 POI 規則 | Spec-06, Spec-07, Spec-08 | `application/batch_process_service.py`, `services/google_maps_api_service.py` |
| BR-04 批次回呼 | Spec-09 | `services/dataflow_service.py`, `utils/pubsub_services.py` |
| BR-05 post-batch | Spec-09 | `application/batch_process_service.py`, `sql/failed_retry_list.sql`, `sql/flatten_geo_data.sql` |
| BR-06 Geocoding 串接 | Spec-10, Spec-11, Spec-12, Spec-13 | `services/geocoding_flow_service.py`, `application/geocoding_batch_process_service.py`, `sql/geocoding_*.sql` |
| BR-07 Geocoding 致命錯誤 | Spec-14 | `application/geocoding_batch_process_service.py`, `services/google_maps_api_service.py` |

## 4.2 Spec -> 測試檔案 對照

| Spec | 現有測試 |
| --- | --- |
| Spec-03 Pub/Sub 204 | `tests/test_geocoding_route.py` |
| Spec-10 階段切換 | `tests/test_geocoding_flow.py` |
| Spec-11/12 update SQL 條件 | `tests/test_geocoding_batch_service.py` |
| Spec-13 最終匿名化通知 | `tests/test_geocoding_flow.py`, `tests/test_geocoding_edge_case.py` |
| Spec-14 致命錯誤中止 | `tests/test_geocoding_batch_service.py`, `tests/test_geocoding_flow.py` |

## 4.3 目前缺口

- Spec-01/02 的 Place Aggregate 入口測試缺口較大。
- Spec-04/05 的 SQL 去重與排除規則尚未有完整自動化斷言。
- Spec-09 的 flatten 成功/失敗分支需補整合測試。

## 4.4 變更檢查清單

當以下檔案異動時，需同步檢查 BR/Spec：

- `services/dataflow_service.py`
- `application/batch_process_service.py`
- `services/geocoding_flow_service.py`
- `application/geocoding_batch_process_service.py`
- `sql/get_geo_query_data*.sql`
- `sql/failed_retry_list.sql`
- `sql/flatten_geo_data.sql`
- `sql/geocoding_*.sql`
