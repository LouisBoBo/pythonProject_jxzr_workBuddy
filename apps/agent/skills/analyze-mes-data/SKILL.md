---
name: analyze-mes-data
description: >-
  跨平台 MES 数据分析（通用）：在制/急单、分布汇总、出图、值班/异常日报。
  用户说「分析一下」「出图」「柱状图」「饼图」「日报」「急单分布」「按状态各多少」
  且要查当前资料包实时数据时启用。口径与分组由资料包配置，换平台不改代码。
  禁止用 pcb-domain-chat 编造厂内数字。PCB 行业扩展见 metric_packs 与 analyze-pcb-mes。
---

# MES 数据分析（资料包驱动）

## 硬原则

1. **不写死实体 id / 路径 / 状态枚举** — 一律以当前 `list_platform_entities` / `list_query_metrics` 为准  
2. **先取数，再出图**：`query_metric` / `summarize` / `analyze_platform_brief` / `analyze_time_trend` → `render_analysis_chart`  
3. **图表类型自动选，禁止追问用户用什么图**  
   - 用户点名（柱状图/折线图/饼图）→ 最高优先  
   - 趋势/走势/环比同比 → `line`（「最近N天趋势」优先 `analyze_time_trend`，自带折线）  
   - 分布/占比/构成 → `pie`  
   - 其余对比/各多少 → `bar`（默认）  
   - 调用时传 `user_intent=用户原话`，`chart_type` 可留 `auto`  
4. 绑不上如实说，引导补 OpenAPI 或在资料包放 `metrics.json` / `analysis.json`  
5. 页内汇总须说明「本次 returned / 非全库」
6. 无日期列时**禁止**编造「最近 N 天」坐标轴；`analyze_time_trend` 会诚实失败并 caveat

## 换平台怎么配（实施）

| 文件 | 作用 |
|------|------|
| `entities.json` | OpenAPI 导入，可查对象 |
| `metrics.json` | 按 id **覆盖**口径的 entity_hints / 枚举 |
| `analysis.json` | `group_by_labels`、`brief_metric_ids`、`metric_packs` |
| `ops_scenes.json` | 覆盖值班场景别名/是否出图 |
| `profile.json` | 可写 `"metric_packs": ["pcb"]` 加载行业可选包 |

详见 `docs/MES业务/资料包分析配置说明.md`。

## 推荐链路

| 意图 | 工具 |
|------|------|
| 在制 / 急单 / 当日完工 | `query_metric` 或 `run_ops_scene` |
| 按某字段各多少 | `summarize_platform_data`（group_by 用中文角色名，工具映射真实列） |
| 最近 N 天/周趋势 | `analyze_time_trend`（`grain=day|week`，可选 `value_field` 求和；无日期列诚实失败） |
| 概况 / 异常分布 | `analyze_platform_brief` |
| 出图（勿问用什么图） | `render_analysis_chart(groups=…, user_intent=用户原话)`；前端自动出图，勿再贴 fence/重复表 |
| PCB/品质运营看板 | `run_analysis_demo(playbook='pcb-ops-board')`（「打开PCB运营看板」）；多图+可选简报/急单；勿用「早会演示」话术 |
| 仅渲染看板模板 | `render_analysis_dashboard(template_id='pcb_ops', user_intent=用户原话)` |
| 异常日报 | `run_ops_scene('plant-exception-daily')` |
| 值班简报 | `run_ops_scene('ops-daily-brief')` |
| 跨表对账（开关开启） | `readonly_sql` → 再出图 |

## 自检

- [ ] 未沿用上一套 MES 的实体 id  
- [ ] 出图 series 来自工具；未追问用户图表类型  
- [ ] 缺实体/缺字段时未编造  
