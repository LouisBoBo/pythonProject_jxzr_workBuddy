# 04 · MES 表结构业务能力摸底

> **一句话**：你把厂方表结构说明（`schema.md`）上传进资料包 → 在对话里问「MES 能干什么、工单到入库串哪些表」→ Agent 只读本地文档，用人话能力地图 / 场景表包 / 摸底报告回答。  
> **不是**：假装查了实时库行数；也不是拿能力地图里的 capability id / 代表表名去当 `query_platform_data` 的 entity（那是功能 02 查数路径）。

---

## 1. 实现原理

### 1.1 我们到底实现了什么？

实施同事常问：「这套 MES 理论上能管哪些事？工单下达到入库要经过哪些表？」  
这类问题应该看**已上传的表结构文档**，不是打生产接口数行数。  
所以做了 **表结构业务能力摸底**：人上传一次 `schema.md`，对话里按固定工具链读本地资料包，出中文能力地图与场景串表。

| 人配的 / 人问的 | 系统干的 | 达到的效果 |
|----------------|----------|------------|
| 上传表结构 `.md` | 写入当前资料包 `schema.md`，清索引缓存 | 对话与设置页读同一份目录 |
| 「MES 能干什么」 | `list_platform_capabilities` 等 | 模块 + 代表表，中文人话 |
| 「工单到入库哪些表」 | `get_scenario_table_pack` | 阶段表包；文档没写则 missing |
| 「资料包齐了吗」 | `inspect_mes_profile` | `known` / `missing`，分层 A/B/C |
| 「导出摸底报告」 | `export_schema_survey_report` | Markdown / Excel 落 `EXPORT_DIR` |

**技术落点（整包）：**

| 层次 | 路径 |
|------|------|
| 业务工具 | `apps/agent/tools/schema_tool/` |
| Skill | `apps/agent/skills/analyze-mes-schema/SKILL.md` |
| 资料包 API | `apps/api/routes/mes_profile.py`（前缀 `/api/mes-profile`） |
| 资料包解析 | `apps/agent/mes_profile.py` → `get_active_profile_dir()` |
| 前端（上传） | `SettingsView.vue`、`api.js`（`uploadMesSchema` / `activateMesProfile`） |
| 落盘 | `data/mes_profiles/{MES_PROFILE_ID}/schema.md` 等 |

### 1.2 和「MES 查数」（功能 02）差在哪？

很多人一听「MES」就把摸底和查数混成一件事。这里要掰开：

| | **摸底（本篇）** | 查数 / 导出（功能 02） |
|--|------------------|------------------------|
| 问什么 | 文档里有哪些模块/表/场景 | 今天有多少工单等**实时行** |
| 数据来源 | `schema.md`（+ 可选 `capability_map.json`） | `entities.json` ← OpenAPI |
| 工具族 | `schema_tool/*` | `query_tool/*` |
| Skill | `analyze-mes-schema` | `query-mes-data` |
| 会不会打 MES HTTP | **默认不打**（仅 `compare_schema_vs_catalog(sample_live=true)` 可选抽检） | 必打（JWT + `PLATFORM_BASE_URL`） |
| ID 语义 | capability id / 表名 | **entity id**（OpenAPI 路径） |

设置页也是一套资料包、两套用途：上传表结构给摸底；上传 OpenAPI / entities 给查数。对照用 `compare_schema_vs_catalog`，结论仍要写清「文档视角 ≠ 已查实时库」。

**技术上怎么隔开：**

| 点 | 实现 |
|----|------|
| Skill 禁混 | `analyze-mes-schema`：摸底问题**只调** `schema_tool/*`，禁止为「有哪些模块」调 `query_platform_data` |
| 能力地图声明 | `list_platform_capabilities` 等：`scope=schema_only`，输出标明依据是已上传文档 |
| 表结构检索注记 | `describe_schema_table` / `list_schema_*`：note 写明「不能直接用 `query_platform_data` 查此表，除非已进 entities.json」 |
| 换厂防串 | `PUT /api/mes-profile/active` + `inspect_mes_profile`；旧会话里的 entity/表名不得沿用 |

### 1.3 为什么要「能力地图」还要「场景表包」？

**人话：**  
- 能力地图 → 领导听得懂「有哪些模块、代表表是啥」。  
- 场景表包 → 实施要串流程：「工单下达→入库」文档里写了哪些表；没写就 missing，**禁止猜表名**。

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 解析索引 | `mes_schema_parser.build_index` | 读本地 MD → 域/表摘要；按 path+mtime 缓存 |
| 换厂推断 | `schema_infer.infer_capabilities_from_index` | 无 `capability_map.json` 时按域自动推断，不写死厂名 |
| 人话总览 | `capability_map.list_platform_capabilities` | 有 JSON 覆盖则用之，否则 inferred |
| 单模块展开 | `describe_platform_capability` | 按 id/说法展开模块+代表表 |
| 术语 | `list_platform_glossary` | 通用术语 + 文档表中文名 |
| 场景 | `business_scenarios.get_scenario_table_pack` | 内置场景 ∪ 资料包 JSON；种子不在文档则 missing |

### 1.4 资料包自检分层钉死了什么？

| 约束 | 技术实现 |
|------|----------|
| 摸底只看表结构层 | `inspect_mes_profile` → `A_schema`；查数看 `B_query`；运维看 `C_ops` |
| 缺什么直说 | 返回 `known[]` / `missing[]` / `can_answer_now` |
| 凭证不进 prompt | 只返回账号是否已填，不回密钥 |
| 路径不越界 | 上传走 `resolve` + 限制在 `DATA_DIR` |
| 上传后热重置 | `_reload_after_profile_change` / `invalidate_schema_caches` |

---

## 2. 实现流程（人话 + 技术点怎么落地）

> 每节先讲「人看到什么 / 为什么这样」，再给 **技术点表** 和调用链。

### 2.1 人怎么把表结构装进资料包？

**人话：** 设置页「上传表结构及 API 接口」→ 选厂方 `.md` → 激活当前资料包。对话里摸底读的就是这份目录；换厂要重新激活，别沿用旧会话里的表名。

```text
SettingsView.vue
  ├─ 上传表结构 → api.uploadMesSchema
  │     → POST /api/mes-profile/upload-schema
  │     → 写入 data/mes_profiles/{id}/schema.md（≤25MB，UTF-8）
  │     → invalidate_schema_caches / _reload_after_profile_change
  ├─ 激活资料包 → api.activateMesProfile
  │     → PUT /api/mes-profile/active
  │     → 写 settings.json 的 MES_PROFILE_ID
  └─（查数用，对照摸底）upload-openapi / entities → 功能 02
```

**技术点：**

| 点 | 怎么做的 |
|----|----------|
| 当前厂 | `MES_PROFILE_ID`；`get_active_profile_dir()` |
| 可选覆盖 | `MES_SCHEMA_DOC` 可指向其它 schema 路径 |
| 旁路索引 | `DATA_DIR/schema/mes_schema_index.json`（`INDEX_CACHE`） |
| 可选人话覆盖 | `capability_map.json` / `business_scenarios.json` / `schema_catalog_map.json` |

---

### 2.2 资料包齐不齐，怎么先自检？

**人话：** 换厂或刚上传后，先问「资料包配齐了吗」。系统分层告诉你：表结构有没有（摸底）、entities/账号有没有（查数）——缺哪层说哪层，不把查数缺项说成摸底也能答。

```text
用户：「资料包配齐了吗？」
  → Skill analyze-mes-schema
  → inspect_mes_profile()          # profile_readiness.py
       清缓存重读
       → A_schema / B_query / C_ops
       → known[] / missing[] / can_answer_now
  → can_answer_now=false 则先停，引导补缺
```

**技术点：**

| 点 | 函数 | 怎么做的 |
|----|------|----------|
| 分层就绪 | `inspect_mes_profile` | 摸底只依赖 `A_schema` |
| 每轮上下文 | `format_mes_context_block` | 注入平台/表结构/实体/账号是否齐（无密钥） |
| 偏查数刷新 | `refresh_mes_profile_from_runtime` | 本机 OpenAPI 合并 entities（**功能 02**） |

---

### 2.3 「MES 能干什么」怎么变成能力地图？

**人话：** Agent 读当前 `schema.md` 索引，优先返回带 `markdown_summary` 的模块列表；要深挖某个模块再 `describe`；术语走 glossary。全程标明「依据已上传文档，不是实时条数」。

```text
「MES 能干什么 / 功能总览」
  → list_platform_capabilities()           # capability_map.py
       → _resolved_map（JSON 或 infer）
       → mes_schema_parser.build_index
  → 可选 describe_platform_capability(focus)
  → 可选 list_platform_glossary(keyword?)
  → 可选 list_schema_domains / list_schema_tables / describe_schema_table
       # schema_query.py：表名检索，仍禁止当 entity 查数
```

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 总览 | `list_platform_capabilities` | `scope=schema_only`；禁止答「ZR WorkBuddy 产品能干什么」 |
| 表检索 | `list_schema_*` / `describe_schema_table` | limit≤80；字段截断；note 禁直接查数 |
| 强制重建 | `rebuild_schema_index` | 文档刚更新时 `force` |
| 启发式能力 | `analyze_schema_capabilities` | 按表前缀/域代表表，仍属文档视角 |

---

### 2.4 「工单到入库」场景表包怎么来的？

**人话：** 先列支持的业务场景，再按场景名取表包；文档里找不到的种子表记 missing，**不许模型编表名**。

```text
「工单下达到入库涉及哪些表？」
  → list_business_scenarios()
  → get_scenario_table_pack(scenario=...)
       → load_business_scenarios（内置 ∪ 资料包 JSON）
       → schema_infer.match_tables_for_stage
       → 可选关联 1–2 跳扩展
  → 返回 tables_found / missing / 关系说明
```

**技术点：**

| 点 | 函数 | 怎么做的 |
|----|------|----------|
| 清单 | `list_business_scenarios` | 含 `tables_found` / `bindable` |
| 表包 | `get_scenario_table_pack` | 精确表名优先，再关键字；非流程引擎 |
| 覆盖 | `business_scenarios.json` | 可覆盖/停用内置场景 |

---

### 2.5 文档 vs 接口对照、导出报告

**人话：** 想知道「表结构写了、OpenAPI 却没暴露」用对照工具（默认**不**打 MES）。要交给实施交接，再导出摸底报告到服务器导出目录。

```text
compare_schema_vs_catalog(sample_live=false)   # schema_diff.py
  → 名称启发式 + 可选 schema_catalog_map.json overlay
  → 匹配 / 仅文档 / 仅接口
  → sample_live=true 时才对已匹配实体 limit=1 抽检（最多 5）

export_schema_survey_report(format=markdown|excel|both)  # schema_report.py
  → 汇总能力地图、场景、术语
  → 写到 EXPORT_DIR，回复绝对路径
```

**技术点：**

| 点 | 函数 | 怎么做的 |
|----|------|----------|
| 默认不连库 | `compare_schema_vs_catalog` | `sample_live` 默认 false |
| 匹配≠同一对象 | 输出说明 | 禁止把对上名字说成「已查实时库」 |
| 报告路径 | `export_schema_survey_report` | 服务端绝对路径，不是浏览器本地 |

---

### 2.6 页面 / API / 对话入口对照

| 你做的事 | 前端 / 入口 | 后端 | 落到的核心 |
|----------|-------------|------|------------|
| 上传表结构 | `uploadMesSchema` | `POST /api/mes-profile/upload-schema` | 写 `schema.md` |
| 激活资料包 | `activateMesProfile` | `PUT /api/mes-profile/active` | `MES_PROFILE_ID` |
| 看资料包状态 | `fetchMesProfile` | `GET /api/mes-profile` | 路径与 source |
| 摸底问答 | 对话 SSE | Skill + `schema_tool/*` | 无单独「/schema-survey」REST |

摸底结论在**聊天气泡**（或导出文件路径）；设置页只负责资料包落盘。OpenAPI tags「MES接入」，summary 为中文。

---

### 2.7 从头到尾一眼版（业务 + 代码）

```text
【设置】upload-schema → schema.md → PUT active
        ↓
【对话】Skill analyze-mes-schema
        ↓
【自检】inspect_mes_profile（A_schema）
        ↓
【读文档】build_index → list_platform_capabilities / 场景表包 / schema_query
        ↓
【可选】compare_schema_vs_catalog（默认不查数）
        ↓
【可选】export_schema_survey_report → EXPORT_DIR
```

与功能 02 对照：

```text
【02】OpenAPI → entities.json
  → list_platform_entities → query_platform_data(entity=…) → 实时行
```

---

### 2.8 出问题时先查哪？

| 现象 | 人话原因 | 技术上先看 |
|------|----------|------------|
| 能力地图空 | 没上传 / 指错厂 | `schema.md` 是否存在；`MES_PROFILE_ID` |
| 和查数结论矛盾 | 混了 Skill / 把文档当行数 | 是否误调 `query_platform_data`；用 `compare_schema_vs_catalog` |
| 换厂后表名全错 | 旧会话 id 沿用 | `PUT active` + 本轮 `inspect_mes_profile` |
| 用能力 id 查数失败 | id 语义不同 | 必须先在当前 `entities.json` 有对应 entity |
| 报告路径打不开 | 看的是服务端路径 | `EXPORT_DIR` 权限与返回的绝对路径 |

---

## 3. 技术及用法（速查）

| 模块 | 关键函数 | 干什么 |
|------|----------|--------|
| `capability_map.py` | `list_platform_capabilities`、`describe_platform_capability`、`list_platform_glossary` | 人话能力地图 / 术语 |
| `schema_query.py` | `list_schema_domains`、`list_schema_tables`、`describe_schema_table`、`rebuild_schema_index` | 表结构检索 |
| `business_scenarios.py` | `list_business_scenarios`、`get_scenario_table_pack` | 业务场景 → 表包 |
| `mes_schema_parser.py` | `build_index`、`find_table_full`、`schema_doc_path` | 解析本地 MD |
| `schema_infer.py` | `infer_capabilities_from_index`、`match_tables_for_stage` | 换厂推断、场景匹配 |
| `schema_diff.py` | `compare_schema_vs_catalog` | 文档 vs 接口目录 |
| `schema_report.py` | `export_schema_survey_report` | 导出摸底报告 |
| `profile_readiness.py` | `inspect_mes_profile` | 资料包分层自检 |
| Skill | `analyze-mes-schema` | 剧本：摸底不走查数 |
| API | `routes/mes_profile.py` | 上传 / 激活资料包 |

**配置：**

| 变量 / 键 | 含义 |
|-----------|------|
| `MES_PROFILE_ID` | 当前激活资料包 |
| `MES_SCHEMA_DOC` | 可选：覆盖 schema 路径 |
| `DATA_DIR` | 资料包根（默认仓库 `data/`） |

**数据文件：** `data/mes_profiles/{id}/schema.md`（摸底主数据）；可选 `capability_map.json`、`business_scenarios.json`；`openapi.json` / `entities.json` 属查数（功能 02）。

操作详述见 [`../MES业务/表结构业务能力分析说明.md`](../MES业务/表结构业务能力分析说明.md)；**实现以本篇为准**。

---

## 4. 后续可以怎么做、不要做什么

**可以做：**

1. 场景包按行业模板可配置（PCB 急单链、品质闭环等）——先扩 `business_scenarios` JSON，再改内置种子  
2. 摸底报告一键贴进实施交接文档（仍只读本地索引）  
3. 与资料包 OpenAPI 自动对齐「文档有、接口无」清单（继续走 `compare_schema_vs_catalog`）  

**不要做：**

1. 用能力地图里的 capability id / 代表表名去 `query_platform_data` 冒充实时条数  
2. 为「有哪些模块」去打 MES HTTP 数行数  
3. 把摸底结论自动当成「已上线接口能力」（须先对照 catalog）  

---

## 自测路径（验收）

1. 上传一份 `schema.md` → 激活 → 问「你们家 MES 有什么功能总览」→ 应有中文能力地图，并标明依据文档。  
2. 问「工单下达到入库涉及哪些表」→ 有表包或明确 missing，**不编表名**。  
3. 问「资料包配齐了吗」→ `inspect_mes_profile` 分层结果合理。  
4. 故意用能力 id 当 entity 查数 → 应失败或被 Skill 拦住，引导走功能 02 的 `entities.json`。  
