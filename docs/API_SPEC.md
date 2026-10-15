# API_SPEC — uSciTec BioAge AI (v1)

* 基础路径：`/api/v1`；交互式文档：`/api/docs`（OpenAPI：`/api/openapi.json`）
* 认证：`Authorization: Bearer <token>`。Sprint 1 使用环境变量 `AUTH_TOKENS` 中配置的静态令牌，计划在后续 Sprint 改为 OIDC。
* 所有响应都带有 `X-Request-ID`；客户端可以在请求中自带此头（仅限字母数字，最长 64 位）。
* 数值字段必须是**有限的 JSON 数字**："45" 这样的字符串、`true`、`NaN`、`Infinity` 都会被拒绝。
* 未定义的字段一律拒绝（`extra=forbid`）。

## 1. 角色与权限

| 权限 | admin | clinician | researcher | viewer |
|---|:-:|:-:|:-:|:-:|
| patient:create | ✓ | ✓ | | |
| patient:read | ✓ | ✓ | ✓ | ✓ |
| lab:write（录入检测、为患者保存计算结果） | ✓ | ✓ | | |
| lab:read | ✓ | ✓ | ✓ | ✓ |
| bioage:compute（临时计算，不保存） | ✓ | ✓ | ✓ | |
| bioage:read | ✓ | ✓ | ✓ | ✓ |
| audit:read | ✓ | | | |

未认证返回 401 `UNAUTHENTICATED`；无权限返回 403 `FORBIDDEN`。

## 2. 错误格式

```json
{
  "status": "rejected" | "error",
  "code": "VALIDATION_FAILED",
  "message": "人类可读信息",
  "errors": [{"code": "CRP_ZERO", "field": "crp", "message": "…", "severity": "error"}],
  "warnings": [...]
}
```

请求结构不正确时，返回 422 `SCHEMA_VALIDATION_FAILED`，其中 `errors[].code` 形如 `SCHEMA_FLOAT_TYPE`。

## 3. POST /bioage/phenoage

计算 Levine 2018 Clinical PhenoAge。`biomarkers` 与 `lab_result_ids` **必须且只能**提供其中一个。

### 请求（直接提供数值）

```json
{
  "chronological_age": 50,
  "biomarkers": {
    "albumin":        {"value": 4.5,  "unit": "g/dL",   "collected_on": "2026-10-10"},
    "creatinine":     {"value": 0.9,  "unit": "mg/dL",  "collected_on": "2026-10-10"},
    "glucose":        {"value": 92,   "unit": "mg/dL",  "collected_on": "2026-10-10"},
    "crp":            {"below_lod": true, "lod": 0.2, "unit": "mg/L", "collected_on": "2026-10-10"},
    "lymphocyte_pct": {"value": 31,   "unit": "%"},
    "mcv":            {"value": 89,   "unit": "fL"},
    "rdw":            {"value": 12.9, "unit": "%"},
    "alp":            {"value": 65,   "unit": "U/L"},
    "wbc":            {"value": 5.8,  "unit": "10^9/L"}
  },
  "patient_id": null
}
```

* `patient_id`：可选。提供时结果会持久化，需要 `lab:write` 权限。
* 各指标可接受的单位见 `GET /bioage/biomarkers` 或 `CLINICAL_MODEL.md` §3。

### 请求（使用已存储的检测记录）

```json
{"chronological_age": 51.5, "patient_id": "<uuid>", "lab_result_ids": ["<uuid>", "... 共 9 个"]}
```

记录必须属于该患者，且每项指标只能出现一次。

### 200 响应

```json
{
  "status": "ok",
  "result_id": "uuid | null",
  "patient_id": "uuid | null",
  "phenoage": 41.889068111149214,
  "phenoage_rounded": 41.9,
  "chronological_age": 50.0,
  "phenoage_minus_chronological_age": -8.11,
  "mortality_score": 0.02247,
  "linear_predictor": -9.068,
  "lod_policy": "lod_div_sqrt2",
  "computed_at": "2026-10-15T08:45:02Z",
  "model": {
    "model_id": "levine_phenoage_2018",
    "model_version": "1.0.0",
    "engine_version": "0.1.0",
    "coefficients_sha256": "5c0cf3b7…",
    "algorithm_source": "Levine ME, et al. … doi:10.18632/aging.101414"
  },
  "inputs": [{
    "code": "crp", "original_value": 1.0, "original_unit": "mg/L", "normalised_unit": "mg/L",
    "canonical_value": 0.1, "canonical_unit": "mg/dL", "conversion_factor": 0.1,
    "quality_status": "valid", "reference_low": 0, "reference_high": 0.5,
    "below_lod": false, "lod_canonical": null, "imputation": null, "collected_on": "2026-10-10"
  }],
  "lab_result_ids": [],
  "warnings": [{"code": "OUT_OF_REFERENCE_RANGE", "field": "glucose", "message": "…", "severity": "warning"}],
  "disclaimer": "仅供研究和内部验证使用 …"
}
```

### 422 响应（不包含任何年龄字段）

```json
{"status": "rejected", "code": "VALIDATION_FAILED", "message": "输入未通过校验，未生成 PhenoAge 结果",
 "errors": [...], "warnings": [...], "inputs": [...]}
```

### 校验错误码

| code | 含义 |
|---|---|
| MISSING_VALUE | 缺少指标或实际年龄 |
| UNIT_MISSING / UNIT_UNKNOWN / UNIT_NOT_ALLOWED | 未提供单位 / 单位无法识别 / 单位不适用于该指标 |
| NOT_A_NUMBER / NEGATIVE_VALUE | 数值不是有限数字 / 数值为负 |
| OUT_OF_PLAUSIBLE_RANGE | 换算后超出可接受范围（附单位提示） |
| CRP_ZERO | CRP = 0，无法取对数 |
| LOD_REQUIRED / LOD_IMPLAUSIBLE / LOD_CONFLICT / LOD_REJECTED / LOD_NOT_SUPPORTED | 检出限相关错误 |
| LAB_DATES_SPAN_TOO_WIDE / FUTURE_DATE | 各指标检测日期相差超过 `MAX_LAB_SPAN_DAYS` / 检测日期在未来 |
| UNKNOWN_BIOMARKER | 未知指标代码 |
| COMPUTATION_FAILED | 数值计算失败（防御性错误码） |

### 警告码（不阻止计算）

`OUT_OF_REFERENCE_RANGE`、`CRP_BELOW_LOD_IMPUTED`、`AGE_OUTSIDE_TRAINING_RANGE`、`PHENOAGE_EXTRAPOLATED`、`COLLECTION_DATE_MISSING`、`COLLECTION_DATE_INCOMPLETE`

## 4. 其他端点

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | /health | 无 | 健康检查 |
| GET | /bioage/biomarkers | bioage:read | 指标目录：单位、范围、模型信息、LOD 策略 |
| GET | /bioage/results/{id} | bioage:read | 已保存结果（含完整溯源信息） |
| POST | /patients | patient:create | `{pseudonym, sex, birth_date?, is_synthetic}`。pseudonym 须匹配 `^[A-Za-z0-9_-]{3,64}$`，重复返回 409 |
| GET | /patients | patient:read | 列表（最多 200 条） |
| GET | /patients/{id} | patient:read | 单个患者 |
| POST | /patients/{id}/labs | lab:write | 批量录入检测（见下）。任一项有错误则整批拒绝，不写入任何记录 |
| GET | /patients/{id}/labs | lab:read | 检测记录 |
| GET | /patients/{id}/overview | lab:read | 患者信息、每项指标的最新值、全部检测记录、计算历史 |
| GET | /audit-logs?limit= | audit:read | 审计日志 |

### POST /patients/{id}/labs

```json
{
  "collected_on": "2026-10-10",
  "source": "manual_entry | lab_import | synthetic",
  "source_detail": "可选，≤255 字符",
  "measurements": [
    {"biomarker": "crp", "value": 1.5, "unit": "mg/L",
     "reference_low": 0, "reference_high": 5, "reference_unit": "mg/L"},
    {"biomarker": "crp", "below_lod": true, "lod": 0.2, "unit": "mg/L"}
  ]
}
```

返回 201 和已保存的记录。每条记录包含原始值和原始单位、模型单位值、换算系数、参考范围及其来源（`lab` 或 `system_default`）、质量状态（`valid`、`out_of_reference_range` 或 `below_lod`）以及质量问题列表。

## 5. 审计

每个读写端点都会写入 `audit_logs`：actor、role、action、resource_type、resource_id、outcome、request_id，以及 details（只含错误码、计数等非临床元数据）。服务层会拒绝在 details 中写入 `value`、`inputs`、`age`、`birth_date`、`pseudonym` 等字段。
