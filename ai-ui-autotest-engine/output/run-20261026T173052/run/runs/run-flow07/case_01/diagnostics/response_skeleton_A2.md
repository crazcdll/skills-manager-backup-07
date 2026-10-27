# 响应浅骨架 — A2

- 接口: POST apihotel.meituan.com/hotelorder/v1/bindvirtualnumber.json
- http_code: 200
- 字段数: 3（深度 ≤4、数组折叠）
- 全量响应: api_evidence_A2.json；精确取值用 response-search --query/--path

response.error.code = 500
response.error.message = 订单与poi不匹配：orderId=5035036077836749951, poiId=52786813
response.traceId = 8254068295482350426
