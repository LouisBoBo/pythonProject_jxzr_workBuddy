---
name: analyze-pcb-mes
description: >-
  PCB 行业向的 MES 数据分析扩展（可选）：工序在制、AOI/报废等。
  须资料包启用 metric_packs 含 pcb，或 metrics.json 自建口径。
  通用分析优先走 analyze-mes-data；本 Skill 不写死任何客户实体 id。
---

# PCB 行业分析扩展

在 **analyze-mes-data** 通用链路上，仅当当前资料包已加载 PCB 指标包（或自建 metrics）时：

1. `list_query_metrics` 看是否出现 `wip-by-process` / `aoi-fail-topn` / `scrap-rate` / `daily-output-overview`  
2. 有则 `query_metric`；无则说明「当前资料包未启用 pcb 包或无匹配实体」，**禁止编造良率**  
3. 「打开PCB运营看板 / 品质看板」优先 `run_analysis_demo(playbook='pcb-ops-board')`：多图+缺口；也可 `render_analysis_dashboard(template_id='pcb_ops')`  
4. 勿再用「早会演示」对外话术；旧说法仍可命中同一编排  
5. 单图仍用 `render_analysis_chart(user_intent=用户原话)`，勿追问图表类型（趋势→折线、分布→饼、默认柱；用户点名优先）  

启用方式（任选）：

```json
// mes_profiles/{平台}/profile.json
{ "metric_packs": ["pcb"] }
```

或把口径写进该平台自己的 `metrics.json`（更灵活，换厂只改资料包）。
