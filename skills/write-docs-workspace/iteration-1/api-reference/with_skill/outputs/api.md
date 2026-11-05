# Orders API 参考

## 概述

本文面向需要调用 Orders API 的开发者，提供端点、请求约束、响应字段和已知错误的参考信息。本文只使用已提供的事实；未提供的字段、取值或行为会明确标注。

**Base URL**：`https://api.example.com`

API 版本体现在路径的 `/v1` 中。除本文列出的信息外，版本兼容策略和废弃流程未提供。

## 鉴权

请求使用以下 HTTP header 鉴权：

```http
Authorization: Bearer $TOKEN
```

示例中的 `$TOKEN` 是环境变量占位符，不是真实凭证。Token 的获取方式、过期时间、刷新方式和所需权限（scope 或角色）未提供。

## 通用约定

### 请求体和响应格式

`POST /v1/orders` 使用包含 `user_id` 和 `amount` 的请求体。请求体的媒体类型未提供；下文使用 JSON 展示请求体。

成功响应的通用媒体类型未提供。错误响应使用 `application/problem+json`，格式遵循 RFC 9457 Problem Details。

### 金额

`amount` 是整数，单位为分，最小值为 `1`。货币种类未提供，因此不能将该值换算为具体货币金额。

### 幂等

创建订单支持 `Idempotency-Key`。幂等键保留 **24 小时**。

幂等键的格式、是否必填、同一幂等键与相同请求体重复提交时的行为，均未提供。已知同一幂等键对应不同请求体时返回 `409`。

### 分页和排序

查询订单支持 cursor 分页：

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---:|---:|---|---|
| `cursor` | 未提供 | 未提供 | 未提供 | 未提供 | 分页游标 |
| `limit` | 未提供 | 未提供 | `20` | 最大值 `100` | 每页数量 |

排序按 `created_at DESC`。游标的格式、下一页游标所在的响应字段、结束条件和排序稳定性未提供。

### 限流

超过限流时返回 `429`，并返回 `Retry-After` header。限流额度、时间窗口、计算维度以及 `Retry-After` 的值格式未提供。

## 端点

### `POST /v1/orders`

创建订单。

**权限**：未提供。

**幂等**：支持 `Idempotency-Key`，保留 24 小时。是否必须发送该 header 未提供。

**副作用**：创建订单。其他副作用未提供。

#### 请求

请求体只有以下字段：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `user_id` | string | 是 | `usr_` 加 16 位 base62 | 下单用户的 ID |
| `amount` | integer | 是 | 最小值为 `1`；单位为分 | 订单金额 |

字段的其他约束未提供。示例中的 `user_id` 是假值。

```bash
curl -X POST 'https://api.example.com/v1/orders' \
  -H 'Authorization: Bearer $TOKEN' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-idempotency-key-001' \
  -d '{
    "user_id": "usr_8fK2mQ0aZx91LpT3",
    "amount": 1999
  }'
```

上例使用 `Content-Type: application/json` 展示 JSON 请求体；服务是否要求该 header 未提供。`Idempotency-Key` 的具体格式未提供，示例值仅用于演示。

#### 响应

成功返回 `201`。响应字段只有 `order_id` 和 `status`。

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| `order_id` | 未提供 | 未提供 | 创建后的订单 ID；格式未提供 |
| `status` | 未提供 | 未提供 | 订单状态；可选值未提供 |

字段具体类型、是否可为 `null` 以及响应媒体类型未提供。以下仅展示字段结构，示例值不是服务已确认的格式或取值：

```json
{
  "order_id": "example-order-id",
  "status": "example-status"
}
```

#### 错误

错误响应使用 `application/problem+json`，遵循 RFC 9457 Problem Details。题目没有提供各错误的实际 `type` URI，因此不能从路径或错误名称推断。下表中的 `type` 均标记为“未提供”。

| 状态码 | `type` | 触发条件 | 调用方处理 |
|---:|---|---|---|
| `400` | 未提供 | 参数校验失败 | 修正请求参数后再发送 |
| `409` | 未提供 | 同一 `Idempotency-Key` 对应不同请求体 | 使用新的幂等键，并确认请求体 |
| `429` | 未提供 | 超过限流 | 根据 `Retry-After` 决定重试时机 |

Problem Details 的 `title`、`detail`、`instance` 和扩展字段未提供。错误示例只能表示 RFC 9457 的字段结构，不能代表实际返回值：

```json
{
  "type": "<未提供>",
  "title": "<未提供>",
  "status": 400,
  "detail": "<未提供>",
  "instance": "<未提供>"
}
```

### `GET /v1/orders`

查询订单，支持 cursor 分页。

**权限**：未提供。

**幂等**：未提供。查询请求是否具有天然幂等性以及是否允许重试，未提供。

**副作用**：未提供。

#### 请求

查询参数如下：

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---:|---:|---|---|
| `cursor` | 未提供 | 未提供 | 未提供 | 未提供 | 分页游标 |
| `limit` | 未提供 | 未提供 | `20` | 最大值 `100` | 每页数量 |

结果按 `created_at DESC` 排序。

```bash
curl --get 'https://api.example.com/v1/orders' \
  -H 'Authorization: Bearer $TOKEN' \
  --data-urlencode 'limit=20'
```

示例未传递 `cursor`。首次查询是否必须省略 `cursor`、游标如何获取和如何请求下一页，未提供。

#### 响应

该端点的成功状态码、响应字段、字段类型、分页游标位置和响应示例均未提供。

#### 错误

题目给出了 `400`、`409` 和 `429` 三种错误，但未说明它们是否适用于本端点，也未提供本端点专属错误。若本端点返回题目列出的错误，错误应使用 `application/problem+json` 并遵循 RFC 9457；各错误的 `type` URI 及 Problem Details 字段值未提供。

## 错误响应格式

所有已知错误均按 RFC 9457 Problem Details 表达，媒体类型为 `application/problem+json`。RFC 9457 中常见的 `type`、`title`、`status`、`detail` 和 `instance` 字段的实际取值，除已知 HTTP 状态码外均未提供。

客户端不应根据 `title` 文案推断错误类型；本文没有提供可供客户端分支使用的稳定 `type` URI。

## 信息缺口

以下信息未在给定材料中提供：

- Token 的申请、过期、刷新和权限要求。
- 请求体和成功响应的媒体类型要求。
- `Idempotency-Key` 的格式、必填性，以及相同请求体重复提交的行为。
- `order_id` 和 `status` 的类型、格式、可空性及 `status` 的可选值。
- `GET /v1/orders` 的成功状态码、响应 schema、响应示例和分页游标返回方式。
- `cursor` 和 `limit` 的字段类型；`cursor` 的格式和结束条件。
- 限流额度、时间窗口、计算维度，以及 `Retry-After` 的值格式。
- 各错误对应的 `type` URI，以及 `title`、`detail`、`instance` 和扩展字段的实际结构。
- API 的兼容性规则、废弃通知和变更日志。
