# 04 · MES 表结构业务能力摸底

> 回答「你们 MES 能干什么、有哪些模块/表、工单到入库串哪些表」——依据**已上传的表结构文档**，不是假装查了实时库。

---

## 1. 实现原理

### 1.1 摸底回答的是「文档里写了什么」，不是「库里有多少条」

实施同事常问：「这套 MES 理论上能管哪些事？工单到入库要经过哪些表？」  
这些问题应该看**表结构说明文档**（你们上传的 `.md`），而不是打生产接口数行数。

所以摸底和查数是**两套工具、两个 Skill**，提示词里禁止混用：

| 问题类型 | 工具族 | 数据来源 |
|----------|--------|----------|
| MES 有哪些模块/表/场景 | `schema_tool/*` | 本地表结构文档 |
| 今天有多少工单 | `query_tool/*` | MES HTTP 实时接口 |

### 1.2 资料包自检：缺什么直说

`inspect_mes_profile` 会检查当前激活资料包：

- 有没有表结构文件  
- 有没有 OpenAPI / entities  
- 接口账号是否配置  

返回 `known`（已知项）和 `missing`（缺什么、去哪补）。  
**换厂后**旧会话里出现的实体 id 不能沿用——必须以本轮资料包为准，防止「江西中软的表名」套到另一家厂。

### 1.3 主要能力块（工具在干什么）

| 能力 | 工具举例 | 输出形态 |
|------|----------|----------|
| 人话能力地图 | `list_platform_capabilities` | 模块 + 代表表，中文 |
| 单模块展开 | `describe_platform_capability` | 某域细节 |
| 业务场景串表 | `get_scenario_table_pack` | 「工单下达→入库」涉及哪些表 |
| 术语表 | `list_platform_glossary` | 字段/缩写解释 |
| 文档 vs 接口 | `compare_schema_vs_catalog` | 表里有但接口没暴露的差集 |
| 导出报告 | `export_schema_survey_report` | Markdown / Excel 文件 |

解析层在 `mes_schema_parser.py`、`schema_infer.py` 等：把 Markdown 表结构切成可检索的结构。

### 1.4 谁在执行？

全程 **Deep Agents 读本地资料包文件**，不连 Cursor，不改业务代码仓。  
设置页上传走 `mes_profile.py` API，与对话里的摸底工具读的是**同一份目录**。

---

## 2. 实现流程（技术点怎么落地）

> 摸底全程 **Deep Agents 读本地资料包**；与 `query_platform_data` 查实时行数严格分离。

### 2.1 资料包落盘与激活（与查数共用目录）

```text
设置页 / API（routes/mes_profile.py）：
  POST /api/mes-profile/upload-schema      → schema.md
  POST /api/mes-profile/upload-openapi     → openapi.json
  PUT  /api/mes-profile/active             → MES_PROFILE_ID
       ↓
data/mes_profiles/{profile_id}/
  ├─ schema.md（或 uploads 下的表结构说明）
  ├─ openapi.json
  └─ entities.json（openapi_to_entities 生成，查数用）
```

| 技术点 | 实现 |
|--------|------|
| 当前厂 | `settings.json` 的 `MES_PROFILE_ID`；`get_active_profile_dir()` |
| 上传校验 | 路径 `resolve` + 限制在 `DATA_DIR` |
| 对话与设置一致 | 摸底 Tool 与 `mes_profile` API 读**同一份**目录 |

### 2.2 自检：`inspect_mes_profile`

```text
用户：「资料包配齐了吗？」
  → Skill analyze-mes-schema
  → inspect_mes_profile()（profile_readiness.py）

检查项 → known[] / missing[]
  - 表结构文件是否存在
  - OpenAPI / entities 是否生成
  - MES_API_* 账号是否配置（提示查数用，摸底本身不连 HTTP）
```

换厂后第一轮常先调此工具，防止旧会话里的实体 id 套错厂。

### 2.3 能力地图与场景串表

```text
「MES 能干什么？」
  → list_platform_capabilities()（capability_map.py）
  → mes_schema_parser / schema_infer 解析 schema.md
  → 模块列表 + 代表表，中文人话

「工单到入库涉及哪些表？」
  → get_scenario_table_pack(scenario=...)（business_scenarios.py）
  → 关键词匹配 schema 内表名
  → 返回表包 + 关系说明；文档没写则 missing，禁止猜表名
```

| 技术点 | 实现 |
|--------|------|
| 术语 | `list_platform_glossary()` |
| 单模块展开 | `describe_platform_capability(capability_id)` |
| 文档 vs 接口 | `compare_schema_vs_catalog()`：表有、OpenAPI 无 → 待开发清单 |

### 2.4 导出摸底报告

```text
export_schema_survey_report(format=markdown|excel)
  → schema_report.py 汇总能力地图、场景、术语
  → 写到 EXPORT_DIR，回复绝对路径
```

### 2.5 Skill 硬边界（`analyze-mes-schema`）

- 摸底问题：**只调** `schema_tool/*`  
- **禁止**为「有哪些模块」去调 `query_platform_data` 数行数  
- 输出须标明依据是**已上传文档**，不是实时库统计

### 2.6 常见排查

| 现象 | 查什么 |
|------|--------|
| 能力地图空 | `schema.md` 是否上传；`MES_PROFILE_ID` |
| 和查数结论矛盾 | 是否混 Skill；应用 `compare_schema_vs_catalog` |
| 换厂后表名全错 | 是否仍指向旧 profile；须 `PUT active` |
| 报告路径打不开 | `EXPORT_DIR` 权限；返回的是服务端绝对路径 |

---

## 3. 技术及用法

| 技术 / 模块 | 怎么用 |
|-------------|--------|
| `tools/schema_tool/capability_map.py` | 人话能力地图 |
| `schema_query.py` / `mes_schema_parser.py` / `schema_infer.py` | 解析与查询表结构 |
| `business_scenarios.py` | 业务场景 → 相关表包 |
| `schema_report.py` | 导出摸底报告 |
| `schema_diff.py` | 表结构 vs 可查对象对照 |
| `profile_readiness.py` | 资料包是否齐 |
| Skill `analyze-mes-schema` | 剧本：摸底不走查数 |
| API `routes/mes_profile.py` | 上传 / 激活资料包 |

配置：当前 `MES_PROFILE_ID` 指向的资料包目录。

---

## 4. 后续扩展与优化建议

1. **可做**：场景包按行业模板可配置（PCB 急单链、品质闭环等）。  
2. **可做**：摸底报告一键贴进实施交接文档。  
3. **慎做**：把摸底结论自动当成「已上线接口能力」（应用 `compare_schema_vs_catalog` 核对）。  
4. **不要做**：用能力地图里的模块名去 `query_platform_data` 冒充实时条数。

---

## 自测话术

- 「你们家 MES 系统有什么功能？给我一个功能总览」  
- 「工单下达到入库大概涉及哪些表？」  
- 「资料包配齐了吗？」  

详见：`docs/MES业务/表结构业务能力分析说明.md`、`MES摸底固定话术.md`。  
