## `〈METHOD〉 /v1/〈resource〉`

〈用一句话说明这个端点做什么。〉〈可选：和相近端点的区别。〉

**权限**：`〈scope〉`
**幂等**：〈支持 `Idempotency-Key`，保留 24 小时 / 天然幂等 / 不幂等，不要自动重试〉
**副作用**：〈发 webhook `order.created`、扣减库存……〉

### 请求

路径参数

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `id` | string | 是 | `ord_` + 16 位 base62 | 订单 ID |

请求体

| 字段 | 类型 | 必填 | 默认 | 约束 | 说明 |
|---|---|---|---|---|---|
| | | | | | |

```bash
curl -X 〈METHOD〉 https://api.example.com/v1/〈resource〉 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 〈uuid〉" \
  -d '{
    "〈field〉": "〈value〉"
  }'
```

### 响应

`〈200/201〉`

| 字段 | 类型 | 可空 | 说明 |
|---|---|---|---|
| | | | |

```json
{
}
```

### 错误

返回 `application/problem+json`（RFC 9457）。

| 状态码 | `type` | 触发条件 | 调用方怎么办 |
|---|---|---|---|
| 400 | `.../problems/validation` | 字段校验失败，见 `errors[].pointer` | 修正参数，不要重试 |
| 404 | `.../problems/not-found` | | |
| 409 | `.../problems/conflict` | 同一幂等键、不同请求体 | 换新的幂等键 |
| 429 | `.../problems/rate-limited` | | 按 `Retry-After` 退避 |
