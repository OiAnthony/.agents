# API 参考文档

## 基本信息

- **Base URL**：`https://api.example.com`
- **鉴权**：在请求中加入以下请求头：

  ```http
  Authorization: Bearer example-token-not-real
  ```

  `example-token-not-real` 是文档示例中的假值。实际请求请替换为你的 token。

本文档只记录已提供的信息。未提供的字段、取值和响应结构不会在文档中补充推测。

## `POST /v1/orders`

创建订单。

### 请求头

| 请求头 | 是否必需 | 说明 |
|---|---:|---|
| `Authorization` | 是 | 使用 Bearer token 鉴权。 |
| `Idempotency-Key` | 否 | 支持幂等请求。幂等键保留 24 小时。 |

### 请求体

请求体只有以下字段：

| 字段 | 是否必填 | 类型 | 约束 |
|---|---:|---|---|
| `user_id` | 是 | 未提供 | 格式为 `usr_` 加 16 位 base62。 |
| `amount` | 是 | 整数 | 以分为单位，最小值为 `1`。 |

示例中的 `user_id` 使用假值：

```json
{
  "user_id": "usr_Ab12Cd34Ef56Gh78",
  "amount": 1999
}
```

> 上例中的用户数据为假值。`amount` 表示整数分。

### 幂等性

- 可通过 `Idempotency-Key` 请求头提交幂等键。
- 幂等键保留 **24 小时**。
- 如果同一幂等键对应不同请求体，服务返回 `409`。

同一幂等键的具体格式未提供。

### 成功响应

成功状态码为 `201`。

响应字段只有：

- `order_id`
- `status`

字段的类型、格式和 `status` 的具体取值未提供。

示例结构（字段值为占位值，不代表实际格式）：

```json
{
  "order_id": "example-order-id",
  "status": "example-status"
}
```

### 请求示例

```http
POST /v1/orders HTTP/1.1
Host: api.example.com
Authorization: Bearer example-token-not-real
Idempotency-Key: example-idempotency-key

{
  "user_id": "usr_Ab12Cd34Ef56Gh78",
  "amount": 1999
}
```

上例中的 token、幂等键和用户数据均为假值或占位值。

## `GET /v1/orders`

查询订单。

### 查询参数

| 参数 | 是否必需 | 说明 |
|---|---:|---|
| `cursor` | 未提供 | 支持 cursor 分页。 |
| `limit` | 否 | 默认值为 `20`，最大值为 `100`。 |

结果按 `created_at DESC` 排序。

`cursor` 的格式、分页响应中的下一页信息，以及查询结果字段未提供。

### 请求示例

不带分页参数：

```http
GET /v1/orders HTTP/1.1
Host: api.example.com
Authorization: Bearer example-token-not-real
```

指定 `limit`：

```http
GET /v1/orders?limit=20 HTTP/1.1
Host: api.example.com
Authorization: Bearer example-token-not-real
```

使用 cursor：

```http
GET /v1/orders?cursor=EXAMPLE_CURSOR&limit=20 HTTP/1.1
Host: api.example.com
Authorization: Bearer example-token-not-real
```

`EXAMPLE_CURSOR` 只是占位值。cursor 的实际格式未提供。

### 响应

GET 接口的成功状态码、响应字段和响应示例未提供。

## 错误处理

错误使用 **RFC 9457 Problem Details** 表达。

错误响应的具体 HTTP `Content-Type`、Problem Details 字段值和响应示例未提供。以下仅列出已知状态码及其含义：

| HTTP 状态码 | 含义 | 触发条件 |
|---:|---|---|
| `400` | 参数校验失败 | 请求参数未通过校验。 |
| `409` | 幂等键冲突 | 同一幂等键对应不同请求体。 |
| `429` | 超过限流 | 请求超过限流，并返回 `Retry-After`。 |

### `429` 的重试信息

`429` 响应会返回 `Retry-After`。该字段的具体值、单位和限流规则未提供。

### RFC 9457 信息缺口

目前未提供以下错误响应细节：

- Problem Details 响应的具体字段和值。
- `type`、`title`、`detail`、`instance` 等字段是否返回。
- 错误响应的 `Content-Type`。
- 每个错误的响应示例。
- `Retry-After` 的具体格式和值。

## 未提供的信息汇总

- 全部接口的请求和响应 `Content-Type` 要求。
- `Authorization` 失败时的状态码和错误响应。
- `POST /v1/orders` 中 `user_id`、`amount`、`order_id` 和 `status` 的完整类型、格式或取值范围（已明确的约束除外）。
- `Idempotency-Key` 的格式及过期后的行为。
- `GET /v1/orders` 的成功状态码和响应字段。
- `cursor` 的格式、生成方式和下一页返回方式。
- 限流的具体阈值、时间窗口和适用范围。
- `Retry-After` 的具体值和单位。
- RFC 9457 Problem Details 的具体字段、值和示例。
