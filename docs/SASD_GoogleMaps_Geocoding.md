# [越南雲端數據中台 / OVS-LX-VDO-01]

# [越南消金新增 Google Maps 地理空間數據 - Geocoding API]

# SA / SD 系統分析與設計文件

---

## 文件制定／修訂履歷

| 制定／修訂版次 | 制定／修訂日期 | 制定／修訂說明 | 作者 | 備註 |
|---|---|---|---|---|
| v0.1 | 2026/02/04 | 初版 | Denny | |
| v0.2 | 2026/02/12 | 調整並完善規格 | Tom | |

---

## 目錄

- [\[越南雲端數據中台 / OVS-LX-VDO-01\]](#越南雲端數據中台--ovs-lx-vdo-01)
- [\[越南消金新增 Google Maps 地理空間數據 - Geocoding API\]](#越南消金新增-google-maps-地理空間數據---geocoding-api)
- [SA / SD 系統分析與設計文件](#sa--sd-系統分析與設計文件)
  - [文件制定／修訂履歷](#文件制定修訂履歷)
  - [目錄](#目錄)
  - [第一章、功能概述 (SA)](#第一章功能概述-sa)
    - [1.1 專案/功能說明](#11-專案功能說明)
    - [1.2 系統/服務流程](#12-系統服務流程)
  - [第二章、API 規格 (SA)](#第二章api-規格-sa)
    - [2.1 基本資訊](#21-基本資訊)
    - [2.2 上行/請求 API 規格](#22-上行請求-api-規格)
    - [2.3 上行/請求 API 範例](#23-上行請求-api-範例)
    - [2.4 下行/回應 API 規格](#24-下行回應-api-規格)
    - [2.5 下行/回應 API 範例](#25-下行回應-api-範例)
    - [2.6 處理結果代碼](#26-處理結果代碼)
  - [第三章、處理邏輯 (SA)](#第三章處理邏輯-sa)
    - [3.1 程式處理流程](#31-程式處理流程)
    - [3.2 檢核下行](#32-檢核下行)
    - [3.3 儲存下行 (GCS)](#33-儲存下行-gcs)
    - [3.4 儲存下行 (BigQuery)](#34-儲存下行-bigquery)
    - [3.5 處理結果代碼](#35-處理結果代碼)
  - [第四章、雲端資源配置與設計 (SD)](#第四章雲端資源配置與設計-sd)
    - [4.1 GCP 資源申請表](#41-gcp-資源申請表)
      - [Cloud Run Job](#cloud-run-job)
      - [Secret Manager](#secret-manager)
      - [Service Account](#service-account)
      - [BigQuery](#bigquery)
      - [GCS](#gcs)
    - [4.2 服務架構暨程式流程圖](#42-服務架構暨程式流程圖)
  - [第五章、非功能性需求設計 (SD)](#第五章非功能性需求設計-sd)
    - [5.1 效能需求](#51-效能需求)
    - [5.2 可用性與可靠性](#52-可用性與可靠性)
    - [5.3 錯誤處理策略](#53-錯誤處理策略)
    - [5.4 快取與去重策略](#54-快取與去重策略)
    - [5.5 安全性](#55-安全性)
    - [5.6 監控與日誌](#56-監控與日誌)
  - [附錄零 — 術語表（Glossary）](#附錄零--術語表glossary)
  - [附錄零 b — BigQuery Schema DDL](#附錄零-b--bigquery-schema-ddl)
  - [第六章、附錄](#第六章附錄)
    - [附錄一 — 通訊地址發查](#附錄一--通訊地址發查)
    - [附錄二 — 戶籍地址發查](#附錄二--戶籍地址發查)
    - [附錄三 — 簽約經緯度發查](#附錄三--簽約經緯度發查)
    - [附錄四 — 更新已發查通訊地址](#附錄四--更新已發查通訊地址)
    - [附錄五 — 更新已發查戶籍地址](#附錄五--更新已發查戶籍地址)
    - [附錄六 — 更新已發查經緯度](#附錄六--更新已發查經緯度)
    - [附錄七 — 下行檢核程式碼](#附錄七--下行檢核程式碼)

---

## 第一章、功能概述 (SA)

### 1.1 專案/功能說明

**API 設計目的與業務應用場景**

串接 Google Maps 地理空間數據服務，作為越南消金業務後續風險分析使用。  
本階段目標在於透過 Google Maps API 將地址轉換成經緯度定位、經緯度轉換成地址定位，進一步識別高風險、違約率偏高的用戶群所屬詳細地點，並以此作為後續驗證團夥詐欺行為的重要依據。

**關聯資料來源**

| 資料來源 | 說明 |
|---|---|
| Google Maps Geocoding API | 外部地理空間服務，提供地址 ↔ 座標轉換 |
| BigQuery - HES | `RAW_HES_DATASET.APPLICATION`、`RAW_HES_DATASET.CUSTOMER`，存有用戶申貸資訊 |
| BigQuery - VMB | `RAW_VMB_DATASET.APPLY_INFO`，存有申貸時的簽約經緯度 |
| BigQuery - EDEP | `RAW_EDEP_DATASET.GEOCODING`，本服務的發查結果儲存目的地 |
| GCS | `gs://ovslxvdo01-{env}-rawdata-api/GOOGLEMAPS/GEOCODING/`，原始 JSON 回應儲存位置 |

**服務性質**

內部使用（東南亞數據團隊開發人員與風險分析師）。

---

### 1.2 系統/服務流程

本服務執行三類地理空間發查，處理流程如下：

```
┌──────────────────────────────────────────────────────────────┐
│  Cloud Run Job (排程觸發，每日執行)                           │
│                                                              │
│  1. 從 BigQuery HES / VMB 取出未發查的客戶資料               │
│     ├─ 通訊地址 (CONTACT_ADDRESS)                            │
│     ├─ 戶籍地址 (RESIDENCE_ADDRESS)                          │
│     └─ 簽約經緯度 (CONTRACT_COORDINATES)                     │
│                                                              │
│  2. 呼叫 Google Maps Geocoding API                           │
│     ├─ address → latlng（地址轉座標）                        │
│     └─ latlng → address（座標轉地址）                        │
│                                                              │
│  3. 下行檢核（格式驗證、必填欄位補全）                        │
│                                                              │
│  4. 儲存結果                                                 │
│     ├─ GCS：原始 JSON 格式                                   │
│     └─ BigQuery：RAW_EDEP_DATASET.GEOCODING                  │
│                                                              │
│  5. 更新已發查紀錄（避免重複發查）                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 第二章、API 規格 (SA)

### 2.1 基本資訊

| 項目 | 內容 |
|---|---|
| API 名稱 | Google Maps : Geocoding API |
| API URI | `https://maps.googleapis.com/maps/api/geocode/json?` |
| HTTP Method | GET |
| Content-Type | application/json |
| 驗證方式 | API Key（由 GCP Secret Manager 管理） |
| 功能描述 | 地址 ↔ 座標轉換、取得詳細地址定位 |
| API 官方文件 | [Google Maps Geocoding API 說明](https://developers.google.com/maps/documentation/geocoding/requests-geocoding?hl=zh-tw) |

---

### 2.2 上行/請求 API 規格

> **注意：** `address` 與 `latlng` 二擇一必填。

| LVL | 欄位名稱 | 資料型態 | 必填 | 最大長度 | 說明 |
|---|---|---|---|---|---|
| 1 | Content-Type | String | N | — | 預設為 `application/json` |
| 1 | key | String | Y | — | Google API 金鑰（由 Secret Manager 注入） |
| 1 | fulfill_on_zero_results | String | N | — | 固定帶 `true`，使回應包含 root-level 結構資訊 |
| 1 | latlng | String | 條件必填 | — | 經緯度，格式為 `"latitude,longitude"` |
| 1 | address | String | 條件必填 | — | 要查詢的地址（URL encoded） |

---

### 2.3 上行/請求 API 範例

**輸入經緯度（座標 → 地址）**

```
GET https://maps.googleapis.com/maps/api/geocode/json?latlng={latlng}&key={API_KEY}&fulfill_on_zero_results=true
```

範例：

```
GET https://maps.googleapis.com/maps/api/geocode/json?latlng=10.8231,106.6297&key=YOUR_API_KEY
```

**輸入地址（地址 → 座標）**

```
GET https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={API_KEY}&fulfill_on_zero_results=true
```

範例：

```
GET https://maps.googleapis.com/maps/api/geocode/json?address=268+Ly+Thuong+Kiet,+Ho+Chi+Minh&key=YOUR_API_KEY
```

---

### 2.4 下行/回應 API 規格

| LVL | 欄位名稱 | 資料型態 | 說明 |
|---|---|---|---|
| 1 | status | string | 請求狀態代碼（見 2.6） |
| 1 | plus_code | dict | Root-level Plus Code 資訊 |
| 2 | compound_code | string | Root-level Plus Code（區域碼，可選） |
| 2 | global_code | string | Root-level 全域 Plus Code（優先取值來源） |
| 1 | results | list | Geocoding 結果列表 |
| 2 | place_id | string | 地點唯一識別碼 |
| 2 | formatted_address | string | 完整格式化地址 |
| 2 | types | list | 地點類型列表 |
| 2 | address_components | list | 地址組成元件列表 |
| 2 | long_name | string | 地址元件全名 |
| 2 | short_name | string | 地址元件縮寫 |
| 2 | types | list | 元件類型（如 `country`、`administrative_area_level_1`） |
| 2 | geometry | dict | 地理幾何資訊 |
| 3 | location | dict | 座標位置 |
| 4 | lat | float | 緯度 |
| 4 | lng | float | 經度 |
| 2 | plus_code | dict | Result-level Plus Code 資訊（fallback 用） |
| 3 | global_code | string | Result-level 全域 Plus Code |

---

### 2.5 下行/回應 API 範例

```json
{
  "plus_code": {
    "compound_code": "3PR4+2QX Thoi An Dong, Can Tho, Vietnam",
    "global_code": "7P273PR4+2QX"
  },
  "results": [
    {
      "address_components": [
        {
          "long_name": "CH Bé Hiền",
          "short_name": "CH Bé Hiền",
          "types": ["establishment", "point_of_interest", "transit_station"]
        },
        {
          "long_name": "Thới An Đông",
          "short_name": "Thới An Đông",
          "types": ["political", "sublocality", "sublocality_level_1"]
        },
        {
          "long_name": "Cần Thơ",
          "short_name": "Cần Thơ",
          "types": ["administrative_area_level_1", "political"]
        },
        {
          "long_name": "Vietnam",
          "short_name": "VN",
          "types": ["country", "political"]
        }
      ],
      "formatted_address": "CH Bé Hiền, Thới An Đông, Cần Thơ, Vietnam",
      "geometry": {
        "location": {
          "lat": 10.08992,
          "lng": 105.70731
        },
        "location_type": "GEOMETRIC_CENTER"
      },
      "place_id": "ChIJu8tlmGiGoDERNDK1hZ-1fmE",
      "plus_code": {
        "global_code": "7P273PQ4+XW"
      },
      "types": ["establishment", "point_of_interest", "transit_station"]
    },
    {
      "address_components": [
        {
          "long_name": "54/8",
          "short_name": "54/8",
          "types": ["street_number"]
        },
        {
          "long_name": "Nguyễn Chí Thanh",
          "short_name": "Nguyễn Chí Thanh",
          "types": ["route"]
        },
        {
          "long_name": "Cần Thơ",
          "short_name": "Cần Thơ",
          "types": ["administrative_area_level_1", "political"]
        },
        {
          "long_name": "Vietnam",
          "short_name": "VN",
          "types": ["country", "political"]
        }
      ],
      "formatted_address": "54/8 Nguyễn Chí Thanh, Thới An Đông, Cần Thơ 900000, Vietnam",
      "geometry": {
        "location": {
          "lat": 10.0897875,
          "lng": 105.7073582
        },
        "location_type": "ROOFTOP"
      },
      "place_id": "ChIJL88gmGiGoDERKjEAUmSdZCU",
      "types": ["premise", "street_address"]
    }
  ],
  "status": "OK"
}
```

---

### 2.6 處理結果代碼

| RETURNCODE | RETURNDESC | 回傳時機 | 建議處理方式 |
|---|---|---|---|
| `OK` | 請求成功，回傳有效結果 | 正常回應 | 繼續儲存下行 |
| `ZERO_RESULTS` | 查詢成功，但沒有符合的結果 | 地址無效或過於模糊 | 仍寫入 GCS 原始回應與 BigQuery 基本欄位（回應欄位為 NULL），供後續追蹤 |
| `OVER_QUERY_LIMIT` | 已超過配額限制 | 可能以 HTTP 429 或 payload status 呈現 | HTTP 429 走指數退避重試（最多 3 次）；若為 payload status 則視為非 OK 回應並跳過 |
| `REQUEST_DENIED` | 請求被拒絕，通常是 API Key 無效或權限不足 | API Key 異常 | 立即告警（PagerDuty / Slack），停止批次 |
| `INVALID_REQUEST` | 請求參數錯誤或缺少必要欄位 | 上行資料缺少 address 或 latlng | 記錄 log，跳過該筆，繼續下一筆 |
| `UNKNOWN_ERROR` | 伺服器端錯誤，請稍後重試 | Google 服務端臨時異常 | 固定間隔重試（30 秒），最多 3 次；重試耗盡後中止批次 |

---

## 第三章、處理邏輯 (SA)

### 3.1 程式處理流程

執行 Geocoding 批次作業時，判斷邏輯如下：

**Step 1 — 取得客戶基本資訊**

取出所有客戶資訊，以下欄位皆不能為 `NULL` 或字串 `"null"`（每筆皆取最新）：

| 資料類型 | 來源欄位 | 發查類型（GEO_TYPE） |
|---|---|---|
| 通訊地址 | `HES.customer.CURRENT_DETAILED_ADDRESS` | `CONTACT_ADDRESS` |
| 戶籍地址 | `HES.customer.PERMANENT_DETAILED_ADDRESS` | `RESIDENCE_ADDRESS` |
| 簽約經緯度 | `VMB.apply_info.LONGITUDE` / `VMB.apply_info.LATITUDE` | `CONTRACT_COORDINATES` |
| 申貸序號 | `HES.application.SERIAL_NUMBER` | — |
| 客戶 ID | `HES.customer.CUID` | — |

**Step 2 — 篩選未發查資料**

目前程式預設由 `GeocodingBatchProcessService.STAGE_SQL` 指向 `sql/test_geocoding_query_*.sql` 進行發查資料載入（測試名單），每批最多 3 筆。

正式查詢版 SQL 仍保留於 `sql/geocoding_query_*.sql`，邏輯上以 `NOT EXISTS` 進行去重。

**Step 3 — 呼叫 Google Maps Geocoding API**

- 通訊地址 / 戶籍地址：以 `address` 欄位發查
- 簽約經緯度：以 `latlng` 欄位發查（格式：`latitude,longitude`，使用來源原始精度）

**Step 4 — 更新已發查資料**

每批次都會先執行對應 update SQL：

- `contact_address`：`sql/geocoding_update_contact_address.sql`
- `residence_address`：`sql/geocoding_update_residence_address.sql`
- `contract_coordinates`：`sql/geocoding_update_contract_coordinates.sql`（目前整份 SQL 以註解停用）

---

### 3.2 檢核下行

可參閱 [附錄七 — 下行檢核程式碼](#附錄七-下行檢核程式碼)，並依實際情形調整。

主要驗證項目：

- `status` 為 `OK` 才進行儲存
- `geometry.location.lat` / `lng` 必須為合法的浮點數
- `formatted_address` 不得為空字串
- `address_components` 必須包含至少一個元件

---

### 3.3 儲存下行 (GCS)

每個 Geocoding 發查完的原始 JSON 回應，儲存至 GCS：

```
gs://ovslxvdo01-{env}-rawdata-api/GOOGLEMAPS/GEOCODING/{data_date}_{serial_number}.json
```

| 參數 | 說明 |
|---|---|
| `{env}` | 環境代碼，如 `dev`、`stg`、`prd` |
| `{data_date}` | 發查日期，格式 `YYYYMMDD` |
| `{serial_number}` | `HES.application.SERIAL_NUMBER` |

---

### 3.4 儲存下行 (BigQuery)

目標資料表：`RAW_EDEP_DATASET.GEOCODING`

| 欄位 | 資料來源 | 欄位說明 |
|---|---|---|
| PARTITION_DATE | 來源 `partition_date + 1 day`（程式邏輯） | 寫入分區日期 |
| CUID | `HES.customer.CUID` | 客戶唯一識別碼 |
| SERIAL_NUMBER | `HES.application.SERIAL_NUMBER` | 申貸序號 |
| CREATED_AT | `HES.application.CREATED_AT` | 申貸建立時間 |
| GEO_TYPE | — | 發查類型：`RESIDENCE_ADDRESS` / `CONTACT_ADDRESS` / `CONTRACT_COORDINATES` |
| REQUEST_LONGITUDE | `VMB.apply_info.LONGITUDE`（僅 CONTRACT_COORDINATES），以字串寫入，其它為 NULL | 請求經度 |
| REQUEST_LATITUDE | `VMB.apply_info.LATITUDE`（僅 CONTRACT_COORDINATES），以字串寫入，其它為 NULL | 請求緯度 |
| REQUEST_ADDRESS | 依 GEO_TYPE：RESIDENCE→`PERMANENT_DETAILED_ADDRESS`；CONTACT→`CURRENT_DETAILED_ADDRESS`；CONTRACT→NULL | 請求地址 |
| RESPONSE_PLACE_ID | 下行 `place_id`，取不到為 NULL | 回應地點 ID |
| RESPONSE_ADDRESS | 下行 `formatted_address`，取不到為 NULL | 回應完整地址 |
| RESPONSE_GLOBAL_CODE | 優先取 root-level `plus_code.global_code`；若無值則取 `results[0].plus_code.global_code`，仍取不到為 NULL | 回應 Plus Code |
| RESPONSE_PLACE_TYPES | 下行 `types`（LIST），以逗號合併為字串，取不到為 NULL | 回應地點類型 |
| RESPONSE_LONGITUDE | 下行 `geometry.location.lng`，以字串寫入，取不到為 NULL | 回應經度 |
| RESPONSE_LATITUDE | 下行 `geometry.location.lat`，以字串寫入，取不到為 NULL | 回應緯度 |
| RESPONSE_COUNTRY | `address_components` 中 `types` 含 `country` 的 `long_name`，取不到為 NULL | 回應國家 |
| RESPONSE_CITY | `address_components` 中 `types` 含 `administrative_area_level_1` 的 `long_name`，取不到為 NULL | 回應城市/省份 |
| RESPONSE_DISTRICT | `address_components` 中 `types` 含 `administrative_area_level_2` 的 `long_name`，取不到為 NULL | 回應縣市/區 |
| RESPONSE_WARD | `address_components` 中 `types` 含 `sublocality_level_1` 的 `long_name`，取不到為 NULL | 回應鄉鎮/街道 |
| RESPONSE_STREET | `address_components` 中 `types` 含 `route` 的 `long_name`，取不到為 NULL | 回應路名 |
| BQ_CREATED_TIME | UTC timestamp 字串（`%Y-%m-%dT%H:%M:%S.%f`） | 建立時間 |
| BQ_UPDATED_TIME | UTC timestamp 字串（`%Y-%m-%dT%H:%M:%S.%f`） | 最後更新時間 |

> 補充：`ZERO_RESULTS` 也會寫入一筆資料，僅保留 request 與 key 欄位，response 欄位多為 NULL。

---

### 3.5 處理結果代碼

同 [2.6 處理結果代碼](#26-處理結果代碼)。

---

## 第四章、雲端資源配置與設計 (SD)

### 4.1 GCP 資源申請表

> **說明：** 以下為本服務所需的 GCP 資源規格，需向 GCP 管理員申請並確認環境設定。

#### Cloud Run Job

| 項目 | 規格 | 備註 |
|---|---|---|
| 服務名稱 | `geocoding-job` | 依環境加上 `-dev` / `-stg` / `-prd` 後綴 |
| 映像檔來源 | GCR / Artifact Registry | `{region}-docker.pkg.dev/{project}/geocoding/geocoding-job:{tag}` |
| 執行方式 | Cloud Run Job（排程觸發） | |
| 排程 | 每日 01:00 VNT（UTC+7）| Cloud Scheduler 設定 |
| 記憶體 | 2 GiB | 批次處理大量資料時的基本需求 |
| CPU | 2 vCPU | |
| 逾時時間 | 3600 秒（1 小時） | 視資料量可調整至 7200 秒 |
| 最大重試次數 | 3 | 失敗後自動重試 |
| 執行環境 | 第二代執行環境 | |
| VPC 連接 | 需連接至 Private VPC | 用於存取內部 BigQuery / GCS |

#### Secret Manager

| 金鑰名稱 | 說明 | 存取帳號 |
|---|---|---|
| `googlemaps-api-key` | Google Maps Geocoding API 金鑰 | `geocoding-sa@{project}.iam.gserviceaccount.com` |

#### Service Account

| 項目 | 規格 |
|---|---|
| 帳號名稱 | `geocoding-sa@{project}.iam.gserviceaccount.com` |
| 角色 | `roles/bigquery.dataEditor`（EDEP dataset）、`roles/bigquery.dataViewer`（HES、VMB dataset）、`roles/storage.objectCreator`（GCS bucket）、`roles/secretmanager.secretAccessor` |

#### BigQuery

| 項目 | 規格 | 備註 |
|---|---|---|
| Dataset | `RAW_EDEP_DATASET` | 已存在，需申請寫入權限 |
| Table | `GEOCODING` | 若不存在需依 3.4 欄位定義建立 |
| 資料分區 | 依 `PARTITION_DATE` 分區 | 建議使用 DATE 分區提升查詢效能 |
| 資料保留 | 依資料治理規範（建議 3 年） | |

#### GCS

| 項目 | 規格 | 備註 |
|---|---|---|
| Bucket | `ovslxvdo01-{env}-rawdata-api` | 已存在，需申請 objectCreator 權限 |
| 路徑 | `GOOGLEMAPS/GEOCODING/` | |
| 物件命名格式 | `{data_date}_{serial_number}.json` | |
| 存取控制 | Uniform bucket-level access | |
| 資料保留 | 依資料治理規範（建議 90 天後轉 Nearline） | |

---

### 4.2 服務架構暨程式流程圖

```
                        ┌──────────────────────────────────────┐
                        │        Cloud Scheduler（每日 01:00）  │
                        └──────────────────┬───────────────────┘
                                           │ 觸發
                                           ▼
                        ┌──────────────────────────────────────┐
                        │         Cloud Run Job                 │
                        │         geocoding-job                 │
                        │                                       │
  ┌─────────────┐  查詢  │  Step 1: 取未發查客戶清單             │
  │  BigQuery   │◄──────│  (HES application/customer, VMB)     │
  │  HES / VMB  │──────►│                                       │
  └─────────────┘  回傳  │  Step 2: 迴圈發查每筆資料             │
                        │         └─ 呼叫 Google Maps API      │
  ┌─────────────┐        │                                       │
  │Secret Mgr   │──────►│  API Key 注入                         │
  └─────────────┘        │                                       │
                        │  Step 3: 檢核下行                     │
  ┌─────────────┐  儲存  │                                       │
  │    GCS      │◄──────│  Step 4a: 儲存原始 JSON 至 GCS        │
  └─────────────┘        │                                       │
  ┌─────────────┐  寫入  │  Step 4b: 寫入結構化欄位至 BigQuery   │
  │  BigQuery   │◄──────│  (RAW_EDEP_DATASET.GEOCODING)         │
  │    EDEP     │        │                                       │
  └─────────────┘        └──────────────────────────────────────┘
                                           │
                                    呼叫外部API
                                           ▼
                        ┌──────────────────────────────────────┐
                        │     Google Maps Geocoding API         │
                        │  maps.googleapis.com/maps/api/geocode │
                        └──────────────────────────────────────┘
```

---

## 第五章、非功能性需求設計 (SD)

### 5.1 效能需求

| 項目 | 目標值 | 說明 |
|---|---|---|
| 每次作業處理筆數 | 無上限（依當日新增資料量） | 批次全量處理 |
| 單筆 API 呼叫回應時間 | ≤ 500 ms（P95） | 依 Google Maps SLA |
| 每日作業完成時間 | ≤ 2 小時 | 需於 03:00 VNT 前完成，供早盤風控分析使用 |
| API 呼叫速率 | 依 `qpm_limit` 控制（目前環境多為 1200 QPM） | 程式以 QPM 節流（`min_interval = 60 / qpm_limit`） |

> **配額管理：** 每日 Geocoding API 呼叫上限依 GCP 專案設定，預設免費額度為 40,000 次/月（超出按量計費）。若每日資料量超過 1,300 筆，需評估升級為付費方案或申請配額提升。

> **效能可行性驗算（以 1200 QPM 為例）：**
>
> - 作業時間限制：01:00 → 03:00 VNT = **2 小時 = 120 分鐘**
> - QPM 上限：1,200 次/分鐘（約 20 QPS）
> - 理論最大處理量：1,200 × 120 = **144,000 筆/日**（未扣除重試與網路延遲）
> - 若每日新增資料遠超此上限，需評估：a) 提高配額，或 b) 分批執行（多個 Job）

---

### 5.2 可用性與可靠性

| 項目 | 目標值 | 說明 |
|---|---|---|
| 服務可用性 | ≥ 99.0%（月度計算） | Cloud Run Job 不常駐，無需 SLA 監控；可用性以「排程作業成功率」衡量 |
| 作業成功率 | ≥ 99.5%（每日） | 單日作業失敗率不超過 0.5% |
| 失敗重試機制 | Cloud Run Job 最多重試 3 次 | 適用於整個 Job 失敗的情況 |

---

### 5.3 錯誤處理策略

| 錯誤類型 | 重試策略 | 告警 | 備註 |
|---|---|---|---|
|  HTTP `429/5xx` | 指數退避（約 1s → 2s → 4s，加上隨機小數），最多 3 次 | 若重試後仍失敗，記錄錯誤 | Client 層重試邏輯 |
| `OVER_QUERY_LIMIT`（payload status） | 不額外重試 | 記錄 log 並跳過 | 目前視為非 `OK` 回應 |
| `UNKNOWN_ERROR` | 固定間隔重試（30s），最多 3 次 | 連續失敗後中止批次 | `REQUEST_DENIED` 同為致命錯誤 |
| `REQUEST_DENIED` | 不重試 | 立即告警（高優先級），停止整批作業 | API Key 失效或配額耗盡 |
| `INVALID_REQUEST` | 不重試 | 記錄 log，跳過該筆 | 上行資料問題，非 API 問題 |
| `ZERO_RESULTS` | 不重試 | 寫入 BigQuery 與 GCS（回應欄位多為 NULL） | 地址無法解析但保留稽核軌跡 |
| 網路逾時 | 立即重試（最多 3 次） | 若連續失敗，記錄錯誤 | timeout 由設定檔控制（預設 30 秒） |

---

### 5.4 快取與去重策略

為避免對同一地址或座標重複呼叫 Google Maps API（節省配額與費用），已在 SQL 邏輯中實作去重：

- **通訊地址 / 戶籍地址：** 以兩層 `NOT EXISTS` 去重（`SERIAL_NUMBER`、`REQUEST_ADDRESS`）
- **簽約經緯度：** 以兩層 `NOT EXISTS` 去重（`SERIAL_NUMBER`、`REQUEST_LONGITUDE` + `REQUEST_LATITUDE`）
- **SERIAL_NUMBER 去重：** 同一申貸序號若已有任一類型的發查紀錄，亦不重複發查

---

### 5.5 安全性

| 項目 | 措施 |
|---|---|
| API Key 管理 | 儲存於 GCP Secret Manager，不硬編碼於程式碼或環境變數 |
| 最小權限原則 | Service Account 僅授予必要的 BigQuery / GCS / Secret Manager 角色 |
| 資料傳輸加密 | 所有 Google Maps API 呼叫強制使用 HTTPS |
| 內網存取 | Cloud Run Job 透過 VPC Connector 存取 BigQuery / GCS，不開放公網 |
| API Key 輪換 | 建議每 90 天輪換一次，輪換期間使用雙金鑰策略避免服務中斷 |

---

### 5.6 監控與日誌

| 項目 | 工具 | 監控指標 |
|---|---|---|
| 作業成功/失敗 | Cloud Monitoring + Cloud Run Job 狀態 | Job 執行狀態、失敗次數 |
| API 呼叫量 | Cloud Monitoring | 每日 Geocoding API 呼叫次數、配額使用率 |
| 錯誤率 | Cloud Logging | `REQUEST_DENIED`、`OVER_QUERY_LIMIT` 錯誤頻率 |
| 資料寫入量 | BigQuery 查詢 | 每日新增至 `GEOCODING` 的資料筆數 |
| 告警通知 | Cloud Monitoring Alerts → Slack / Email | `REQUEST_DENIED` 立即告警；連續失敗超過閾值時告警 |

---

## 附錄零 — 術語表（Glossary）

| 術語 | 全名 / 說明 |
|---|---|
| **SASD** | System Analysis & System Design，系統分析與設計文件 |
| **HES** | Hire Enterprise System，越南消金核心貸款系統 |
| **VMB** | Vietnam Mobile Banking，越南行動銀行申貸系統 |
| **EDEP** | External Data Exchange Platform，外部數據交換平台（本服務的結果儲存位置） |
| **CUID** | Customer Unique ID，客戶唯一識別碼 |
| **SERIAL_NUMBER** | 申貸序號，來自 `HES.APPLICATION.SERIAL_NUMBER`，唯一識別每一筆申貸案件 |
| **GEO_TYPE** | Geocoding 發查類型：`CONTACT_ADDRESS`（通訊地址）/ `RESIDENCE_ADDRESS`（戶籍地址）/ `CONTRACT_COORDINATES`（簽約經緯度） |
| **Geocoding** | 地理編碼，將地址字串轉換為經緯度座標 |
| **Reverse Geocoding** | 反向地理編碼，將經緯度座標轉換為地址字串 |
| **QPM** | Queries Per Minute，每分鐘查詢次數（程式節流使用的速率單位） |
| **VNT** | Vietnam Time，越南標準時間（UTC+7） |
| **env** | 環境代碼：`dev`（開發）/ `stg`（測試）/ `prd`（正式） |
| **RESPONSE_ADDRESS** | Geocoding 下行 `formatted_address` 對應欄位（現行程式與 SQL 皆使用此拼字） |

---

## 附錄零 b — BigQuery Schema DDL

```sql
CREATE TABLE IF NOT EXISTS `RAW_EDEP_DATASET.GEOCODING` (
    PARTITION_DATE      DATE          NOT NULL OPTIONS(description="發查日期，BQ 預設 CURRENT_DATE()"),
    CUID                STRING        NOT NULL OPTIONS(description="客戶唯一識別碼"),
    SERIAL_NUMBER       STRING        NOT NULL OPTIONS(description="申貸序號"),
  CREATED_AT          TIMESTAMP              OPTIONS(description="申貸建立時間，來自 HES.APPLICATION.CREATED_AT"),
    GEO_TYPE            STRING        NOT NULL OPTIONS(description="發查類型: CONTACT_ADDRESS / RESIDENCE_ADDRESS / CONTRACT_COORDINATES"),
  REQUEST_LONGITUDE   STRING                 OPTIONS(description="請求經度，僅 CONTRACT_COORDINATES 有值"),
  REQUEST_LATITUDE    STRING                 OPTIONS(description="請求緯度，僅 CONTRACT_COORDINATES 有值"),
    REQUEST_ADDRESS     STRING                 OPTIONS(description="請求地址，地址類型發查時有值"),
    RESPONSE_PLACE_ID   STRING                 OPTIONS(description="Google Maps place_id"),
    RESPONSE_ADDRESS     STRING                 OPTIONS(description="完整格式化地址（formatted_address）"),
    RESPONSE_GLOBAL_CODE STRING               OPTIONS(description="Plus Code global_code"),
    RESPONSE_PLACE_TYPES STRING               OPTIONS(description="types LIST，以逗號合併為字串"),
  RESPONSE_LONGITUDE  STRING                 OPTIONS(description="回應經度 geometry.location.lng"),
  RESPONSE_LATITUDE   STRING                 OPTIONS(description="回應緯度 geometry.location.lat"),
    RESPONSE_COUNTRY    STRING                 OPTIONS(description="國家名稱（address_components type=country）"),
    RESPONSE_CITY       STRING                 OPTIONS(description="城市/省份（administrative_area_level_1）"),
    RESPONSE_DISTRICT   STRING                 OPTIONS(description="縣市/區（administrative_area_level_2）"),
    RESPONSE_WARD       STRING                 OPTIONS(description="鄉鎮/街道（sublocality_level_1）"),
    RESPONSE_STREET     STRING                 OPTIONS(description="路名（route）"),
  BQ_CREATED_TIME     DATETIME               OPTIONS(description="BQ 建立時間"),
  BQ_UPDATED_TIME     DATETIME               OPTIONS(description="BQ 更新時間")
)
PARTITION BY PARTITION_DATE
OPTIONS(
    description="Google Maps Geocoding 發查結果資料表",
    partition_expiration_days=1095  -- 3 年保留
);
```

---

## 第六章、附錄

### 附錄一 — 通訊地址發查

```sql
WITH latest_hes_application AS (
  SELECT
    id,
    serial_number,
    created_at,
    PARTITION_DATE AS partition_date,
    customer_id,
    BQ_UPDATED_TIME
  FROM `RAW_HES_DATASET.APPLICATION`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_hes_customer AS (
  SELECT
    id,
    cuid,
    current_application_id,
    current_detailed_address
  FROM `RAW_HES_DATASET.CUSTOMER`
  WHERE UPPER(COALESCE(current_detailed_address, 'NULL')) != 'NULL'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
)
SELECT
  appl.serial_number,
  appl.created_at,
  appl.partition_date,
  cust.cuid,
  cust.current_detailed_address AS request_address,
  CAST(NULL AS FLOAT64) AS request_longitude,
  CAST(NULL AS FLOAT64) AS request_latitude
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
  AND appl.id = cust.current_application_id
WHERE NOT EXISTS (
  SELECT 1
  FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
  WHERE geo_coding.GEO_TYPE = 'CONTACT_ADDRESS'
    AND geo_coding.SERIAL_NUMBER = appl.serial_number
)
  AND NOT EXISTS (
    SELECT 1
    FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
    WHERE geo_coding.GEO_TYPE = 'CONTACT_ADDRESS'
      AND UPPER(COALESCE(geo_coding.REQUEST_ADDRESS, 'NULL')) != 'NULL'
      AND geo_coding.REQUEST_ADDRESS = cust.current_detailed_address
  )
ORDER BY serial_number DESC
LIMIT 500
```

---

### 附錄二 — 戶籍地址發查

```sql
WITH latest_hes_application AS (
  SELECT
    id,
    serial_number,
    created_at,
    PARTITION_DATE AS partition_date,
    customer_id,
    BQ_UPDATED_TIME
  FROM `RAW_HES_DATASET.APPLICATION`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_hes_customer AS (
  SELECT
    id,
    cuid,
    current_application_id,
    permanent_detailed_address
  FROM `RAW_HES_DATASET.CUSTOMER`
  WHERE UPPER(COALESCE(permanent_detailed_address, 'NULL')) != 'NULL'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
)
SELECT
  appl.serial_number,
  appl.created_at,
  appl.partition_date,
  cust.cuid,
  cust.permanent_detailed_address AS request_address,
  CAST(NULL AS FLOAT64) AS request_longitude,
  CAST(NULL AS FLOAT64) AS request_latitude
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
  AND appl.id = cust.current_application_id
WHERE NOT EXISTS (
  SELECT 1
  FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
  WHERE geo_coding.GEO_TYPE = 'RESIDENCE_ADDRESS'
    AND geo_coding.SERIAL_NUMBER = appl.serial_number
)
  AND NOT EXISTS (
    SELECT 1
    FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
    WHERE geo_coding.GEO_TYPE = 'RESIDENCE_ADDRESS'
      AND UPPER(COALESCE(geo_coding.REQUEST_ADDRESS, 'NULL')) != 'NULL'
      AND geo_coding.REQUEST_ADDRESS = cust.permanent_detailed_address
  )
ORDER BY serial_number DESC
LIMIT 500
```

---

### 附錄三 — 簽約經緯度發查

```sql
WITH latest_hes_application AS (
  SELECT
    id,
    serial_number,
    created_at,
    PARTITION_DATE AS partition_date,
    customer_id,
    BQ_UPDATED_TIME
  FROM `RAW_HES_DATASET.APPLICATION`
  WHERE status = 'ACTIVE'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_hes_customer AS (
  SELECT
    id,
    cuid,
    current_application_id
  FROM `RAW_HES_DATASET.CUSTOMER`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_vmb_apply_info AS (
  SELECT
    cuid,
    SAFE_CAST(longitude AS FLOAT64) AS longitude,
    SAFE_CAST(latitude AS FLOAT64) AS latitude
  FROM `RAW_VMB_DATASET.APPLY_INFO`
  WHERE UPPER(COALESCE(longitude, 'NULL')) != 'NULL'
    AND UPPER(COALESCE(latitude, 'NULL')) != 'NULL'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
)
SELECT
  appl.serial_number,
  appl.created_at,
  appl.partition_date,
  cust.cuid,
  CAST(NULL AS STRING) AS request_address,
  CAST(apply_info.longitude AS STRING) AS request_longitude,
  CAST(apply_info.latitude AS STRING) AS request_latitude
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
  AND appl.id = cust.current_application_id
JOIN latest_vmb_apply_info AS apply_info
  ON cust.cuid = apply_info.cuid
WHERE NOT EXISTS (
  SELECT 1
  FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
  WHERE geo_coding.GEO_TYPE = 'CONTRACT_COORDINATES'
    AND geo_coding.SERIAL_NUMBER = appl.serial_number
)
  AND NOT EXISTS (
    SELECT 1
    FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
    WHERE geo_coding.GEO_TYPE = 'CONTRACT_COORDINATES'
      AND SAFE_CAST(geo_coding.REQUEST_LONGITUDE AS FLOAT64) IS NOT NULL
      AND SAFE_CAST(geo_coding.REQUEST_LATITUDE AS FLOAT64) IS NOT NULL
      AND SAFE_CAST(geo_coding.REQUEST_LONGITUDE AS FLOAT64) = apply_info.longitude
      AND SAFE_CAST(geo_coding.REQUEST_LATITUDE AS FLOAT64) = apply_info.latitude
  )
ORDER BY serial_number DESC
LIMIT 500
```

---

### 附錄四 — 更新已發查通訊地址

```sql
-- 參照 SASD 附錄四：更新已發查通訊地址
INSERT INTO `RAW_EDEP_DATASET.GEOCODING` (
  PARTITION_DATE,
  CUID,
  SERIAL_NUMBER,
  CREATED_AT,
  GEO_TYPE,
  REQUEST_ADDRESS,
  RESPONSE_PLACE_ID,
  RESPONSE_ADDRESS,
  RESPONSE_GLOBAL_CODE,
  RESPONSE_PLACE_TYPES,
  RESPONSE_LONGITUDE,
  RESPONSE_LATITUDE,
  RESPONSE_COUNTRY,
  RESPONSE_CITY,
  RESPONSE_DISTRICT,
  RESPONSE_WARD,
  RESPONSE_STREET,
  BQ_CREATED_TIME,
  BQ_UPDATED_TIME
)
WITH latest_hes_application AS (
  SELECT
    id,
    serial_number,
    created_at,
    PARTITION_DATE AS partition_date,
    customer_id,
    BQ_UPDATED_TIME
  FROM `RAW_HES_DATASET.APPLICATION`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_hes_customer AS (
  SELECT
    id,
    cuid,
    current_application_id,
    current_detailed_address
  FROM `RAW_HES_DATASET.CUSTOMER`
  WHERE UPPER(COALESCE(current_detailed_address, 'NULL')) != 'NULL'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
geocoding_serial_number_list AS (
  SELECT DISTINCT serial_number
  FROM `RAW_EDEP_DATASET.GEOCODING`
  WHERE GEO_TYPE = 'CONTACT_ADDRESS'
),
distinct_address AS (
  SELECT DISTINCT
    REQUEST_ADDRESS,
    RESPONSE_PLACE_ID,
    RESPONSE_ADDRESS,
    RESPONSE_GLOBAL_CODE,
    RESPONSE_PLACE_TYPES,
    RESPONSE_LONGITUDE,
    RESPONSE_LATITUDE,
    RESPONSE_COUNTRY,
    RESPONSE_CITY,
    RESPONSE_DISTRICT,
    RESPONSE_WARD,
    RESPONSE_STREET
  FROM `RAW_EDEP_DATASET.GEOCODING`
  WHERE GEO_TYPE = 'CONTACT_ADDRESS'
    AND UPPER(COALESCE(RESPONSE_ADDRESS, 'NULL')) != 'NULL'
)
SELECT
  CURRENT_DATE(),
  cust.cuid,
  appl.serial_number,
  appl.created_at,
  'CONTACT_ADDRESS',
  cust.current_detailed_address,
  geo_coding.RESPONSE_PLACE_ID,
  geo_coding.RESPONSE_ADDRESS,
  geo_coding.RESPONSE_GLOBAL_CODE,
  geo_coding.RESPONSE_PLACE_TYPES,
  geo_coding.RESPONSE_LONGITUDE,
  geo_coding.RESPONSE_LATITUDE,
  geo_coding.RESPONSE_COUNTRY,
  geo_coding.RESPONSE_CITY,
  geo_coding.RESPONSE_DISTRICT,
  geo_coding.RESPONSE_WARD,
  geo_coding.RESPONSE_STREET,
  DATETIME(SAFE_CAST(appl.created_at AS TIMESTAMP), 'UTC'),
  CURRENT_DATETIME('UTC')
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
  AND appl.id = cust.current_application_id
LEFT JOIN geocoding_serial_number_list AS ser_list
  ON appl.serial_number = ser_list.serial_number
LEFT JOIN distinct_address AS geo_coding
  ON cust.current_detailed_address = geo_coding.REQUEST_ADDRESS
WHERE ser_list.serial_number IS NULL
  AND geo_coding.REQUEST_ADDRESS IS NOT NULL
```

---

### 附錄五 — 更新已發查戶籍地址

```sql
-- 參照 SASD 附錄五：更新已發查戶籍地址
INSERT INTO `RAW_EDEP_DATASET.GEOCODING` (
  PARTITION_DATE,
  CUID,
  SERIAL_NUMBER,
  CREATED_AT,
  GEO_TYPE,
  REQUEST_ADDRESS,
  RESPONSE_PLACE_ID,
  RESPONSE_ADDRESS,
  RESPONSE_GLOBAL_CODE,
  RESPONSE_PLACE_TYPES,
  RESPONSE_LONGITUDE,
  RESPONSE_LATITUDE,
  RESPONSE_COUNTRY,
  RESPONSE_CITY,
  RESPONSE_DISTRICT,
  RESPONSE_WARD,
  RESPONSE_STREET,
  BQ_CREATED_TIME,
  BQ_UPDATED_TIME
)
WITH latest_hes_application AS (
  SELECT
    id,
    serial_number,
    created_at,
    PARTITION_DATE AS partition_date,
    customer_id,
    BQ_UPDATED_TIME
  FROM `RAW_HES_DATASET.APPLICATION`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_hes_customer AS (
  SELECT
    id,
    cuid,
    current_application_id,
    permanent_detailed_address
  FROM `RAW_HES_DATASET.CUSTOMER`
  WHERE UPPER(COALESCE(permanent_detailed_address, 'NULL')) != 'NULL'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
geocoding_serial_number_list AS (
  SELECT DISTINCT serial_number
  FROM `RAW_EDEP_DATASET.GEOCODING`
  WHERE GEO_TYPE = 'RESIDENCE_ADDRESS'
),
distinct_address AS (
  SELECT DISTINCT
    REQUEST_ADDRESS,
    RESPONSE_PLACE_ID,
    RESPONSE_ADDRESS,
    RESPONSE_GLOBAL_CODE,
    RESPONSE_PLACE_TYPES,
    RESPONSE_LONGITUDE,
    RESPONSE_LATITUDE,
    RESPONSE_COUNTRY,
    RESPONSE_CITY,
    RESPONSE_DISTRICT,
    RESPONSE_WARD,
    RESPONSE_STREET
  FROM `RAW_EDEP_DATASET.GEOCODING`
  WHERE GEO_TYPE = 'RESIDENCE_ADDRESS'
    AND UPPER(COALESCE(RESPONSE_ADDRESS, 'NULL')) != 'NULL'
)
SELECT
  CURRENT_DATE(),
  cust.cuid,
  appl.serial_number,
  appl.created_at,
  'RESIDENCE_ADDRESS',
  cust.permanent_detailed_address,
  geo_coding.RESPONSE_PLACE_ID,
  geo_coding.RESPONSE_ADDRESS,
  geo_coding.RESPONSE_GLOBAL_CODE,
  geo_coding.RESPONSE_PLACE_TYPES,
  geo_coding.RESPONSE_LONGITUDE,
  geo_coding.RESPONSE_LATITUDE,
  geo_coding.RESPONSE_COUNTRY,
  geo_coding.RESPONSE_CITY,
  geo_coding.RESPONSE_DISTRICT,
  geo_coding.RESPONSE_WARD,
  geo_coding.RESPONSE_STREET,
  DATETIME(SAFE_CAST(appl.created_at AS TIMESTAMP), 'UTC'),
  CURRENT_DATETIME('UTC')
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
  AND appl.id = cust.current_application_id
LEFT JOIN geocoding_serial_number_list AS ser_list
  ON appl.serial_number = ser_list.serial_number
LEFT JOIN distinct_address AS geo_coding
  ON cust.permanent_detailed_address = geo_coding.REQUEST_ADDRESS
WHERE ser_list.serial_number IS NULL
  AND geo_coding.REQUEST_ADDRESS IS NOT NULL
```

---

### 附錄六 — 更新已發查經緯度

```sql
-- -- 參照 SASD 附錄六：更新已發查經緯度
-- INSERT INTO `RAW_EDEP_DATASET.GEOCODING` (
--   PARTITION_DATE,
--   CUID,
--   SERIAL_NUMBER,
--   CREATED_AT,
--   GEO_TYPE,
--   REQUEST_LONGITUDE,
--   REQUEST_LATITUDE,
--   RESPONSE_PLACE_ID,
--   RESPONSE_ADDRESS,
--   RESPONSE_GLOBAL_CODE,
--   RESPONSE_PLACE_TYPES,
--   RESPONSE_LONGITUDE,
--   RESPONSE_LATITUDE,
--   RESPONSE_COUNTRY,
--   RESPONSE_CITY,
--   RESPONSE_DISTRICT,
--   RESPONSE_WARD,
--   RESPONSE_STREET,
--   BQ_CREATED_TIME,
--   BQ_UPDATED_TIME
-- )
-- WITH latest_hes_application AS (
--   SELECT
--     id,
--     serial_number,
--     created_at,
--     PARTITION_DATE AS partition_date,
--     customer_id,
--     BQ_UPDATED_TIME
--   FROM `RAW_HES_DATASET.APPLICATION`
--   QUALIFY ROW_NUMBER() OVER (
--     PARTITION BY id
--     ORDER BY BQ_UPDATED_TIME DESC
--   ) = 1
-- ),
-- latest_hes_customer AS (
--   SELECT
--     id,
--     cuid
--   FROM `RAW_HES_DATASET.CUSTOMER`
--   QUALIFY ROW_NUMBER() OVER (
--     PARTITION BY cuid
--     ORDER BY BQ_UPDATED_TIME DESC
--   ) = 1
-- ),
-- latest_vmb_apply_info AS (
--   SELECT
--     cuid,
--     ROUND(SAFE_CAST(longitude AS FLOAT64), 4) AS longitude,
--     ROUND(SAFE_CAST(latitude AS FLOAT64), 4) AS latitude
--   FROM `RAW_VMB_DATASET.APPLY_INFO`
--   WHERE SAFE_CAST(longitude AS FLOAT64) IS NOT NULL
--     AND SAFE_CAST(latitude AS FLOAT64) IS NOT NULL
--   QUALIFY ROW_NUMBER() OVER (
--     PARTITION BY cuid
--     ORDER BY BQ_UPDATED_TIME DESC
--   ) = 1
-- ),
-- geocoding_serial_number_list AS (
--   SELECT DISTINCT serial_number
--   FROM `RAW_EDEP_DATASET.GEOCODING`
--   WHERE GEO_TYPE = 'CONTRACT_COORDINATES'
-- ),
-- distinct_coordinates AS (
--   SELECT DISTINCT
--     REQUEST_LONGITUDE,
--     REQUEST_LATITUDE,
--     RESPONSE_PLACE_ID,
--     RESPONSE_ADDRESS,
--     RESPONSE_GLOBAL_CODE,
--     RESPONSE_PLACE_TYPES,
--     RESPONSE_LONGITUDE,
--     RESPONSE_LATITUDE,
--     RESPONSE_COUNTRY,
--     RESPONSE_CITY,
--     RESPONSE_DISTRICT,
--     RESPONSE_WARD,
--     RESPONSE_STREET
--   FROM `RAW_EDEP_DATASET.GEOCODING`
--   WHERE GEO_TYPE = 'CONTRACT_COORDINATES'
--     AND UPPER(COALESCE(REQUEST_LONGITUDE, 'NULL')) != 'NULL'
--     AND UPPER(COALESCE(REQUEST_LATITUDE, 'NULL')) != 'NULL'
-- )
-- SELECT
--   DATE_ADD(appl.partition_date, INTERVAL 1 DAY),
--   cust.cuid,
--   appl.serial_number,
--   appl.created_at,
--   'CONTRACT_COORDINATES',
--   CAST(apply_info.longitude AS STRING),
--   CAST(apply_info.latitude AS STRING),
--   geo_coding.RESPONSE_PLACE_ID,
--   geo_coding.RESPONSE_ADDRESS,
--   geo_coding.RESPONSE_GLOBAL_CODE,
--   geo_coding.RESPONSE_PLACE_TYPES,
--   geo_coding.RESPONSE_LONGITUDE,
--   geo_coding.RESPONSE_LATITUDE,
--   geo_coding.RESPONSE_COUNTRY,
--   geo_coding.RESPONSE_CITY,
--   geo_coding.RESPONSE_DISTRICT,
--   geo_coding.RESPONSE_WARD,
--   geo_coding.RESPONSE_STREET,
--   DATETIME(SAFE_CAST(appl.created_at AS TIMESTAMP), 'UTC'),
--   CURRENT_DATETIME('UTC')
-- FROM latest_hes_application AS appl
-- JOIN latest_hes_customer AS cust
--   ON appl.customer_id = cust.id
-- JOIN latest_vmb_apply_info AS apply_info
--   ON cust.cuid = apply_info.cuid
-- LEFT JOIN geocoding_serial_number_list AS ser_list
--   ON appl.serial_number = ser_list.serial_number
-- LEFT JOIN distinct_coordinates AS geo_coding
--   ON apply_info.longitude = SAFE_CAST(geo_coding.REQUEST_LONGITUDE AS FLOAT64)
--  AND apply_info.latitude = SAFE_CAST(geo_coding.REQUEST_LATITUDE AS FLOAT64)
-- WHERE ser_list.serial_number IS NULL
--   AND geo_coding.REQUEST_LONGITUDE IS NOT NULL
--   AND geo_coding.REQUEST_LATITUDE IS NOT NULL
```

---

### 附錄七 — 下行檢核程式碼

```python
def validate_geocoding_response(response: dict) -> bool:
    """
    驗證 Google Maps Geocoding API 下行回應是否有效。
    回傳 True 表示資料有效，可儲存；False 表示跳過。
    """
    status = response.get("status")

    if status != "OK":
        return False

    results = response.get("results", [])
    if not results:
        return False

    result = results[0]

    # 必填欄位驗證
    if not result.get("formatted_address"):
        return False

    geometry = result.get("geometry", {})
    location = geometry.get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")

    if lat is None or lng is None:
        return False

    try:
        float(lat)
        float(lng)
    except (ValueError, TypeError):
        return False

    address_components = result.get("address_components", [])
    if not address_components:
        return False

    return True


def extract_address_component(address_components: list, target_type: str) -> str | None:
    """
    從 address_components 中取出指定類型的 long_name。
    """
    for component in address_components:
        if target_type in component.get("types", []):
            return component.get("long_name")
    return None
```
