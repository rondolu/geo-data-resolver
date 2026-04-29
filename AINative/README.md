# AINative

此資料夾維護 Geo Data Resolver 的 BDD/SDD 工件，內容已同步到目前程式流程：

1. Place Aggregate 批次（`/`、`/get_data_range`）
2. Geocoding 三階段（`/geocoding`）

## 文件清單

- `1-business-requirements.md`
  - 業務需求、流程邊界與成功標準。
- `2-specs-and-acceptance-tests.md`
  - Given/When/Then 規格與可執行驗收點。
- `3-automation-tests-plan.md`
  - 自動化測試策略與落地順序。
- `4-implementation-traceability.md`
  - 需求、規格、程式與測試的對照矩陣。

## 維護規則

- 當 SQL、流程服務、路由有調整時，先更新 `1` 與 `2`。
- PR 建議標註受影響的 BR 與 Spec 編號。
- 若新增流程階段，需同步更新 traceability 文件。
