# Orders API 参考

本文面向需要调用订单 API 的开发者。内容只包含给定材料中的事实；材料未提供的字段、取值和行为会明确标注为“材料未提供”。

## 概述

| 项目 | 值 |
|---|---|
| Base URL | `https://api.example.com` |
| 资源 | 订单（orders） |
| 版本 | `/v1`，其他版本信息材料未提供 |
|

## 鉴权

请求使用 `Authorization` header，格式如下：

```http
Authorization: Bearer $TOKEN
```

示例中的 `$TOKEN` 是环境变量占位符，不是实际凭证。凭证的获取、过期和刷新方式，材料未提供。

## 通用约定

### 请求和响应

本文的请求示例使用 JSON 请求体，并显式设置 `Content-Type: application/json`。给定材料未说明该 header 是否为服务端必需，也未提供其他请求或响应媒体类型约定。

### 幂等键

`POST /v1/orders` 支持 `Idempotency-Key` header。幂等键保留 **24 小时**。

当同一幂等键对应不同请求体时，返回 `409`。相同幂等键对应相同请求体时的返回行为，材料未提供。

### 分页和排序

`GET /v1/orders` 支持 cursor 分页：

- `limit` 默认值为 `20`。
- `limit` 最大值为 `100`。
- 排序为 `created_at DESC`。
- `cursor` 的具体格式、下一页字段、结束条件和无效 cursor 的处理方式，材料未提供。

### 错误表达

错误使用 RFC 9457 Problem Details 作为表达模型。RFC 9457 的标准成员可以包括 `type`、`title`、`status`、`detail` 和 `instance`；本服务对这些字段的具体值、是否全部返回以及扩展字段的约定，材料未提供。

材料也未提供错误响应的 `Content-Type`，因此本文不据此断言服务使用 `application/problem+json`。

错误对象可按以下结构理解。尖括号内容是占位符，不是服务返回值或字段格式承诺：

```json
{
  "type": "<type URI，材料未提供>",
  "title": "<title，材料未提供>",
  "status": 400,
  "detail": "<detail，材料未提供>",
  "instance": "<instance，材料未提供>"
}
```

## `POST /v1/orders`

创建订单。

### 请求头

| Header | 必填 | 说明 |
|---|---:|---|
| `Authorization` | 是 | 使用 `Bearer $TOKEN`。 |
| `Idempotency-Key` | 否 | 该端点支持。保留 24 小时。 |
|

### 请求体

请求体只有以下两个字段：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---:|---|---|
| `user_id` | string | 是 | 格式为 `usr_` 加 16 位 base62 | 下单用户的 ID，例如 `usr_8fK2mQ0aZx91LpT3`。 |
| `amount` | integer | 是 | 整数分，最小值为 `1` | 金额使用分表示。 |
|

未提供其他请求字段。`user_id` 和 `amount` 的额外长度、范围或空值规则，材料未提供。

### 请求示例

```bash
curl --request POST \
  --url 'https://api.example.com/v1/orders' \
  --header 'Authorization: Bearer $TOKEN' \
  --header 'Idempotency-Key: example-key-20261105-001' \
  --header 'Content-Type: application/json' \
  --data '{
    "user_id": "usr_8fK2mQ0aZx91LpT3",
    "amount": 1250
  }'
```

示例中的 `user_id`、`Idempotency-Key` 和金额是文档用假值。给定材料未规定幂等键的格式；示例值不代表格式要求。

### 成功响应

成功返回 `201`。

响应字段只有以下两个字段：

| 字段 | 约束 |
|---|---|
| `order_id` | 字段存在；类型、格式和取值材料未提供。 |
| `status` | 字段存在；类型、枚举值和取值材料未提供。 |
|

示例仅用于展示字段名称。占位值不代表 `order_id` 或 `status` 的实际格式和枚举：

```http
HTTP/1.1 201 Created
```

```json
{
  "order_id": "<fake-order-id>",
  "status": "<status>"
}
```

### 错误

| HTTP 状态码 | 触发条件 | 调用方处理 |
|---:|---|---|
| `400` | 参数校验失败。具体错误字段和校验消息材料未提供。 | 修改请求参数后重试。 |
| `409` | 同一 `Idempotency-Key` 对应不同请求体。 | 不要使用同一幂等键提交不同请求体；具体恢复方式材料未提供。 |
| `429` | 超过限流。该错误是否适用于此端点，材料未明确。 | 按 `Retry-After` 指示等待后再尝试；具体限流额度、窗口和维度材料未提供。 |
|

错误响应采用通用的 RFC 9457 Problem Details 模型；`type`、`title`、`detail`、`instance` 和扩展字段的实际内容材料未提供。

### 幂等和重试

该端点支持 `Idempotency-Key`，保留 24 小时。同一幂等键对应不同请求体时返回 `409`。

网络超时、重复提交、相同幂等键对应相同请求体时是否可以安全重试，以及 24 小时后的行为，材料未提供。

## `GET /v1/orders`

查询订单列表。

### 请求头

| Header | 必填 | 说明 |
|---|---:|---|
| `Authorization` | 是 | 使用 `Bearer $TOKEN`。 |
|

### 查询参数

| 参数 | 类型 | 必填 | 默认值 | 约束 | 说明 |
|---|---|---:|---:|---|---|
| `cursor` | 未提供 | 否 | 无 | 支持 cursor 分页；格式材料未提供。 | 用于定位分页位置。 |
| `limit` | integer | 否 | `20` | 最大值为 `100`。最小值和非法值处理材料未提供。 | 控制分页大小。 |
|

结果按 `created_at DESC` 排序。`created_at` 的格式、排序稳定性以及同一时间的并列排序规则，材料未提供。

### 请求示例

```bash
curl --request GET \
  --url 'https://api.example.com/v1/orders?limit=20&cursor=example-cursor' \
  --header 'Authorization: Bearer $TOKEN'
```

`example-cursor` 是假值占位符。cursor 的实际编码格式材料未提供。

### 响应

成功状态码、响应字段、响应体结构和示例，材料未提供。除已知排序和分页约定外，本文不补充响应 schema。

### 错误

已知错误包括：

| HTTP 状态码 | 触发条件 | 调用方处理 |
|---:|---|---|
| `400` | 参数校验失败。该错误是否适用于此端点以及错误字段，材料未明确。 | 修改查询参数后重试。 |
| `429` | 超过限流。该错误是否适用于此端点，材料未明确；响应返回 `Retry-After`。 | 按 `Retry-After` 指示等待后再尝试。 |
|

`409` 的已知触发条件是同一幂等键对应不同请求体。该端点是否使用幂等键，材料未提供，因此不将该错误归属于此端点。

错误响应使用 RFC 9457 Problem Details 表达；具体错误字段和值材料未提供。

## 错误码总表

下表汇总给定材料中的已知错误。材料没有说明每个错误适用于哪个端点时，保留该限制。

| HTTP 状态码 | 含义 | 已知条件 | 响应信息 |
|---:|---|---|---|
| `400` | 参数校验失败 | 请求参数未通过校验。 | RFC 9457 Problem Details；具体字段和值未提供。 |
| `409` | 幂等键冲突 | 同一幂等键对应不同请求体。 | RFC 9457 Problem Details；具体字段和值未提供。 |
| `429` | 超过限流 | 请求超过限流；响应返回 `Retry-After`。 | RFC 9457 Problem Details；具体字段和值未提供。 |
|

`429` 的 `Retry-After` 值格式、等待时间和限流额度材料未提供。

## 材料未提供的信息

以下信息没有在给定材料中定义，调用方不应从本文推断：

- 错误响应的 `Content-Type`，以及是否为 `application/problem+json`。
- RFC 9457 `type` URI、`title`、`detail`、`instance` 的实际值。
- 错误扩展字段、字段级错误结构和具体校验消息。
- `GET /v1/orders` 的成功状态码和完整响应 schema。
- `order_id`、`status` 的类型、格式和 `status` 枚举值。
- `cursor` 的格式、下一页字段、结束条件和无效值处理。
- `limit` 的最小值和非法值处理。
- `created_at` 的时间格式和排序稳定性。
- 限流额度、时间窗口、计算维度和 `Retry-After` 的具体值。
- 相同幂等键对应相同请求体时的行为、可安全重试条件，以及幂等键超过 24 小时后的行为。
- 凭证的获取、过期和刷新方式。
- 订单创建的副作用，例如扣费、通知或 webhook。
- 版本策略、废弃流程和变更通知方式。
- 其他 HTTP 状态码、请求字段、响应字段和端点。

## 变更日志

给定材料未提供变更日期、变更内容、兼容性影响或迁移方法。
