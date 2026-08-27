/** 每日生产运营日报模板指令（与 apps/automations/production_report.py 对齐） */

export const DAILY_PRODUCTION_REPORT_PROMPT =
  '生成【昨日生产运营日报】，面向领导阅读；必须真实查询当前 MES，禁止编造任何数字。\n\n' +
  '【查数步骤】（后台执行，结果写入「要点/细分」，不要把工具名写进正文）\n' +
  '1. inspect_mes_profile(user_intent="昨日生产运营日报")\n' +
  '2. list_query_metrics()\n' +
  '3. 工单：analyze_platform_brief 或 summarize_platform_data(group_by="状态")；query_metric("在制")；' +
  'query_metric("未完工")；query_metric("紧急未完工")；昨日完工用 analyze_time_trend 或 query_platform_data（有日期筛参时）\n' +
  '4. 设备稼动率（优先）：\n' +
  '   - 先 describe_entity 确认是否存在 device-utilization（设备利用率趋势）\n' +
  '   - 有则 query_platform_data(entity="device-utilization", filters={"period": "day"})\n' +
  '   - 返回 labels + values 时：在要点写平均利用率、最高/最低及对应时点；禁止口算 OEE\n' +
  '   - 若 device-oee 有数据，可在细分补充综合 OEE；device-oee 为 0 条则整段不写 OEE\n' +
  '5. 设备产出：query_metric("日产出") — 有数据才输出「设备产出」条\n' +
  '6. 品质：query_metric("工序良率") — 有数据才输出「工序良率」条\n' +
  '7. 内部可用 run_ops_scene("plant-exception-daily") 交叉核对，不要把核对过程写进正文\n\n' +
  '【正文格式】与 PCB 早报完全一致，仅输出查到的条目（编号连续，无数据条目不占号）：\n' +
  '**1. 工单概况**\n' +
  '要点：（一行核心数字，含昨日日期）\n' +
  '细分：（可选，状态分布）\n\n' +
  '**2. 设备稼动率**\n' +
  '要点：（device-utilization 有数据才写；平均/峰值/低谷利用率 %）\n' +
  '细分：（可选，device-oee 有数据才写）\n\n' +
  '**3. 设备产出**\n' +
  '要点：（有产量才写本条）\n\n' +
  '**4. 工序良率**\n' +
  '要点：（有良率才写本条）\n\n' +
  '**5. 需关注**\n' +
  '要点：（1～2 条业务提醒）\n\n' +
  '禁止：Markdown 表格、## 标题、> 引用、工具名/entity id/caveat/数据缺口/数据说明/「无接口」「0 条」类说明、标题外引言。'
