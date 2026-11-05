# Orders API 参考

## 概述

- **Base URL**：`https://api.example.com`
- **鉴权**：请求头 `Authorization: Bearer $TOKEN`
- **接口**：创建订单、查询订单

下文只记录已提供的服务事实。请求和响应的媒体类型、未列出的字段及字段取值范围，见“未提供的信息”。

## 鉴权

调用方在 `Authorization` 请求头中使用 Bearer token：

```http
Authorization: Bearer $TOKEN
```

示例使用环境变量 `$TOKEN`，不包含真实凭证。token 的获取、过期和刷新方式未提供。

## 通用约定

### 幂等键只适用于创建订单

`POST /v1/orders` 支持 `Idempotency-Key`。幂等键保留 **24 小时**。同一幂等键对应不同请求体时返回 `409`。

材料未说明幂等键的格式、相同请求体重复提交时的响应，以及其他端点是否支持该请求头。

### 查询订单使用游标分页

`GET /v1/orders` 支持 `cursor` 分页。`limit` 默认值为 `20`，最大值为 `100`。结果按 `created_at DESC` 排序。

材料未提供游标的编码、结束条件、稳定性保证，以及响应中下一页游标的字段名。

### 错误使用 RFC 9457 Problem Details 表达

错误按 RFC 9457 Problem Details 表达。RFC 9457 规定了错误对象的表达方式，但不代表当前服务一定返回某个媒体类型、字段集合或 `type` URI。

材料未提供当前服务的错误媒体类型，因此本文不把 `application/problem+json` 写成已确认的服务行为。下方 JSON 仅是 RFC 9457 的**规范示例**，不是当前 API 的实际响应样例：

```json
{
  "type": "https://example.invalid/problems/example",
  "title": "示例错误标题",
  "status": 400,
  "detail": "示例错误详情",
  "instance": "/v1/orders/example"
}
```

上例中的 URI 和文本均为假值。当前服务是否返回 `type`、`title`、`detail`、`instance` 或其他扩展字段，材料未提供。

## `POST /v1/orders`

创建订单。

**权限**：材料未提供。

**幂等**：支持 `Idempotency-Key`，保留 24 小时。同一幂等键对应不同请求体时返回 `409`。

**副作用**：材料未提供。

### 请求

请求体只有以下字段：

| 字段 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---:|---|---|---|
| `user_id` | 材料未提供 | 是 | 无 | `usr_` 加 16 位 base62 | 用户标识。示例：`usr_8fK2mQ0aZx91LpT3` |
| `amount` | 整数 | 是 | 无 | 以分为单位，最小值为 `1` | 订单金额 |

请求示例中的用户 ID 是假值。材料未说明请求体媒体类型，因此示例不添加未确认的 `Content-Type` 请求头；实际调用时需按服务要求设置。

```bash
curl -X POST 'https://api.example.com/v1/orders' \
  -H 'Authorization: Bearer $TOKEN' \
  -H 'Idempotency-Key: demo-idempotency-key' \
  --data-raw '{
    "user_id": "usr_8fK2mQ0aZx91LpT3",
    "amount": 1990
  }'
```

`Idempotency-Key` 示例值为假值。材料未提供该字段的格式要求。

### 成功响应

成功状态码为 `201`。响应字段只有 `order_id` 和 `status`。

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `order_id` | 材料未提供 | 材料未提供 | 订单 ID |
| `status` | 材料未提供 | 材料未提供 | 订单状态 |

以下示例只展示已知字段名。字段类型和具体取值未提供，因此使用占位文本，不表示服务接受或返回该具体值：

```json
{
  "order_id": "<fake-order-id>",
  "status": "<status>"
}
```

### 已知错误

该端点可能涉及的已知错误见[错误码](#错误码)。材料未说明这些错误是否覆盖该端点的全部失败情况。

## `GET /v1/orders`

查询订单列表。

**权限**：材料未提供。

**排序**：按 `created_at DESC` 排序。

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---:|---|---|---|
| `cursor` | 材料未提供 | 材料未提供 | 材料未提供 | 用于游标分页 | 游标内容和生成方式未提供 |
| `limit` | 整数 | 材料未提供 | `20` | 最大值 `100` | 每页数量 |

请求示例：

```bash
curl 'https://api.example.com/v1/orders?limit=20' \
  -H 'Authorization: Bearer $TOKEN'
```

带游标的请求示例：

```bash
curl 'https://api.example.com/v1/orders?cursor=<example-cursor>&limit=20' \
  -H 'Authorization: Bearer $TOKEN'
```

`<example-cursor>` 是占位值，不代表实际游标格式。

### 响应

材料未提供成功状态码、响应字段、字段类型、可空性和响应示例。本文不据此推测订单列表的响应结构。

### 已知错误

材料未明确这些错误与本端点的对应关系。已知错误见[错误码](#错误码)。

## 错误码

下表只列出已提供的错误事实。RFC 9457 的 `type` URI、错误标题、详细信息及调用方处理字段均未提供。

| 状态码 | `type` | 已知触发条件 | `Retry-After` | 调用方处理 |
|---:|---|---|---|---|
| `400` | 材料未提供 | 参数校验失败 | 未提及 | 具体处理方式未提供 |
| `409` | 材料未提供 | 同一幂等键对应不同请求体 | 未提及 | 具体处理方式未提供 |
| `429` | 材料未提供 | 超过限流 | 返回 `Retry-After` | 等待时长和重试策略未提供 |

除 `429` 返回 `Retry-After` 这一点外，限流额度、时间窗口、计算维度及其他响应头均未提供。

## 未提供的信息

为避免把规范建议或常见 API 约定写成服务事实，以下信息没有补充推测：

- 请求和响应的媒体类型，包括是否使用 `application/json` 或 `application/problem+json`。
- token 的获取、过期、刷新和权限 scope。
- 两个端点的成功响应状态码（`POST /v1/orders` 的 `201` 除外）。
- `order_id`、`status` 以及 GET 响应中各字段的类型、可空性和具体取值。
- `cursor` 的格式、下一页字段名、结束条件和分页稳定性。
- `Idempotency-Key` 的格式、重复提交的行为，以及保留期满后的行为。
- RFC 9457 响应中的 `type` URI、`title`、`detail`、`instance` 和扩展字段。
- 限流额度、时间窗口、计算维度，以及 `Retry-After` 的具体值格式。
- 订单创建或查询的其他副作用、重试规则、版本策略、废弃流程和变更日志。
