# 2) Specs & Acceptance Tests

本文件把 BR 轉為可驗證規格。編號可用於 PR 與測試案例追蹤。

## 2.1 Place Aggregate 入口規格

### Spec-01 Daily 入口

- Given：呼叫 `POST /`，且非 Pub/Sub payload。
- When：`DataflowService.handle_daily_request()` 執行。
- Then：回傳 `200` 與批次結果 payload。

### Spec-02 Range 入口

- Given：呼叫 `POST /get_data_range`。
- When：缺少 `start_date` 或 `end_date`。
- Then：回 `400 validation_error`。

### Spec-03 Pub/Sub 入口

- Given：路由收到合法 Pub/Sub push 格式。
- When：服務層成功處理。
- Then：路由回 `204`。

## 2.2 SQL 載入規格

### Spec-04 Daily SQL 規則

- Given：`get_geo_query_data.sql`。
- When：執行查詢。
- Then：
  - 僅回傳 `CUID`、`SERIAL_NUMBER` 有效資料。
  - 排除已在 `GEO_DATA` 或 `FAILED_RETRY_LIST` 的序號。
  - 依 `CUID + SERIAL_NUMBER` 去重。

### Spec-05 Range SQL 規則

- Given：`get_geo_query_data_range.sql` 與 `@start_date/@end_date`。
- When：執行查詢。
- Then：只取指定日期區間並去重。

## 2.3 POI 三情境規格

### Spec-06 三情境執行

- Given：一筆來源資料。
- When：處理流程執行。
- Then：必須依序呼叫三個情境 API。

### Spec-07 整筆寫入條件

- Given：某筆資料三情境中任一情境拋出例外。
- When：該筆處理結束。
- Then：
  - 該筆寫入 `GEO_DATA_FAILED_RETRY_LIST`。
  - 該筆不得寫入 `RAW_EDEP_DATASET.GEO_DATA`。

### Spec-08 座標無效行為

- Given：座標格式無效。
- When：呼叫 `get_area_insights()`。
- Then：回傳 `{"count":"null"}` 且不中斷流程。

## 2.4 最後一批規格

### Spec-09 post_batch_processing

- Given：`context.is_last_batch=True`。
- When：`post_batch_processing()` 執行。
- Then：
  1. 先跑 failed-retry 回補
  2. 再跑 `flatten_geo_data.sql`
  3. flatten 成功才發布 geocoding 第一階段

## 2.5 Geocoding 三階段規格

### Spec-10 階段切換

- Given：`task_type=contact_address` 且狀態為 `completed`。
- When：流程服務處理完成。
- Then：發布下一階段 `residence_address` 啟動訊息。

### Spec-11 每批都執行 update SQL

- Given：任一 geocoding 階段（`batch_number>=1`）。
- When：`process_stage()` 執行。
- Then：先執行對應 `geocoding_update_*.sql`。

### Spec-12 非第一批也執行 update SQL

- Given：`batch_number>1`。
- When：`process_stage()` 執行。
- Then：同樣先跑 update SQL，再跑 query + API。

### Spec-13 最終通知

- Given：`contract_coordinates` 階段完成。
- When：流程進入 `_publish_next_action()`。
- Then：發布 anonymization payload：

```json
{"file_list": ["RAW_EDEP_DATASET.GEOCODING"]}
```

### Spec-14 致命錯誤

- Given：Geocoding API 返回 `REQUEST_DENIED` 或 `UNKNOWN_ERROR`。
- When：批次處理該筆資料。
- Then：拋錯中止該批流程。

## 2.6 驗收清單

- AT-01：`/`、`/get_data_range`、`/geocoding` 在 Pub/Sub 模式成功時回 `204`。
- AT-02：Daily SQL 的排除與去重條件成立。
- AT-03：POI 情境例外時整筆不進 RAW。
- AT-04：最後一批執行 flatten，且 flatten 成功後才啟動 geocoding。
- AT-05：Geocoding 三階段依序串接，最終會送匿名化訊息。
