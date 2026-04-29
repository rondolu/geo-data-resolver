# 3) Automation Tests Plan

目標是以「先高風險流程、再補 SQL 規則」的順序擴充測試覆蓋率。

## 3.1 測試分層

- 單元測試
  - API 回應解析、座標驗證、階段轉換邏輯。
- 服務整合測試（Mock 外部依賴）
  - `DataflowService`、`BatchProcessService`、`GeocodingFlowService`。
- SQL 規格測試
  - 驗證關鍵 SQL 的排除、去重、欄位映射。

## 3.2 既有測試盤點

- 已覆蓋：
  - `tests/test_geocoding_route.py`
  - `tests/test_geocoding_flow.py`
  - `tests/test_geocoding_batch_service.py`
  - `tests/test_geocoding_models.py`
  - `tests/test_geocoding_edge_case.py`

- 仍需補強：
  - Place Aggregate 端點與批次流程。
  - SQL 規則驗證（daily/range/failed-retry/flatten）。
  - post-batch 到 geocoding 啟動的完整鏈路斷言。

## 3.3 優先測試案例

### P0

- TC-P0-01：`POST /get_data_range` 缺參數回 `400`。
- TC-P0-02：POI 任一情境失敗時，不可寫 RAW。
- TC-P0-03：`post_batch_processing()` flatten 失敗時，不可發布 geocoding 啟動訊息。
- TC-P0-04：`contract_coordinates` 完成後，必須發布 anonymization 訊息。

### P1

- TC-P1-01：`get_geo_query_data.sql` 排除已處理與 failed-retry 資料。
- TC-P1-02：`failed_retry_list.sql` 僅回最新且非 2xx/success 狀態。
- TC-P1-03：`flatten_geo_data.sql` 的 `scenario_counts` 映射正確。

### P2

- TC-P2-01：大批次下 recall 訊息是否遞增批號。
- TC-P2-02：Geocoding 非致命錯誤可繼續後續資料。

## 3.4 工具與策略

- 測試框架：`pytest` 或現行 `unittest`。
- 外部依賴：用 mock/stub 隔離 `google.cloud.*` 與 HTTP 呼叫。
- 時間相依邏輯：固定日期與時間，避免 flaky。
- SQL 驗證：可用測試資料集或以查詢結果 stub 驗證規則。

## 3.5 建議落地順序

1. 先補 Place Aggregate P0（高風險且目前相對缺口大）。
2. 補 SQL 規則測試（P1）。
3. 再擴充壓力與邊界場景（P2）。
