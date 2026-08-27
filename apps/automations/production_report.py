"""每日生产运营日报：查数步骤 + 早报式输出规范（与前端模板对齐）。"""

DAILY_PRODUCTION_REPORT_PROMPT = """生成【昨日生产运营日报】，面向领导阅读；必须真实查询当前 MES，禁止编造任何数字。

【查数步骤】（后台执行，结果写入「要点/细分」，不要把工具名写进正文）
1. inspect_mes_profile(user_intent="昨日生产运营日报")
2. list_query_metrics()
3. 工单：analyze_platform_brief 或 summarize_platform_data(group_by="状态")；query_metric("在制")；query_metric("未完工")；query_metric("紧急未完工")；昨日完工用 analyze_time_trend 或 query_platform_data（有日期筛参时）
4. 设备稼动率（优先）：
   - 先 describe_entity 确认是否存在 device-utilization（设备利用率趋势）
   - 有则 query_platform_data(entity="device-utilization", filters={"period": "day"})
   - 返回 labels + values 时：在要点写平均利用率、最高/最低及对应时点（如 08:00–20:00 各小时 %）；禁止口算 OEE
   - 若 device-oee 有数据，可在细分补充综合 OEE（可用率/性能率/质量率）；device-oee 为 0 条则整段不写 OEE，不要写「无数据」
5. 设备产出：query_metric("日产出") — 有数据才输出「设备产出」条
6. 品质：query_metric("工序良率") — 有数据才输出「工序良率」条
7. 内部可用 run_ops_scene("plant-exception-daily") 交叉核对，不要把核对过程写进正文

【正文格式】与 PCB 早报完全一致，仅输出查到的条目（编号连续，中间无数据的条目不占号）：
**1. 工单概况**
要点：（一行核心数字，含昨日日期）
细分：（可选，状态分布）

**2. 设备稼动率**
要点：（device-utilization 有数据才写；一行：平均/峰值/低谷利用率 %）
细分：（可选，device-oee 综合 OEE 有数据才写）

**3. 设备产出**
要点：（有产量才写本条）

**4. 工序良率**
要点：（有良率才写本条）

**5. 需关注**
要点：（1～2 条业务提醒）

禁止：Markdown 表格、## 标题、> 引用、工具名/entity id/caveat/数据缺口/数据说明/「无接口」「0 条」类说明、标题外引言。"""

DAILY_PRODUCTION_REPORT_OUTPUT_PREFIX = """
【生产日报排版】（必须遵守，与 PCB 早报同款）
- 正文只用 **1. 标题** + 要点 + 可选细分，共 3～5 条；条目之间空一行。
- 查到什么写什么；查不到 / 0 条 / 无接口 → 该条整段省略，不要解释原因。
- 设备稼动率优先查 device-utilization（period=day），不要只查 device-oee；device-oee 无数据不影响稼动率条。
- 禁止 Markdown 表格（|）、##/###、> 引用、工具名、entity id、filter_fields、caveat、数据缺口、数据说明、交叉核对过程。
- 数字必须来自本轮 MES 工具返回；禁止估算或口算稼动率/OEE。
- 不要写标题外引言（如「所有数据已取齐」）；日期写在第 1 条要点里。

"""
