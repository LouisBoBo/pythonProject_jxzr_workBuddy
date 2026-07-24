# Deep Agents Skills 使用指南

本文说明本项目如何用 **Deep Agents（harness）+ Skills + Tools** 扩展能力，以及你以后如何自己加 Skill。

---

## 1. 先分清三层

| 层 | 是什么 | 本仓库位置 | 何时改 |
|----|--------|------------|--------|
| **Tools** | 可执行函数（真查库、真导入） | `apps/agent/tools/` | 平台有新 API、要写代码调用时 |
| **实体目录** | 实体 id / 别名 / 路径白名单 | `apps/agent/tools/query_tool/entities.json` | 只加标准 CRUD 实体时 |
| **Skills** | 领域剧本（怎么做、何时用哪把工具） | `apps/agent/skills/*/SKILL.md` | 加业务流程、规范、禁忌时 |

关系：

```text
用户说话
  → Agent（Deep Agents harness）
      → 看到 Skills 摘要（name + description）
      → 需要时读取完整 SKILL.md
      → 按剧本调用 Tools
      → Tools 经 platform_api 访问 ERP
```

**Skill 不能代替 Tool。** 只写「去查生产计划」不够，必须已有 `query_platform_data` 等工具。

**不要和 Cursor IDE 的 Skill 混淆。**  
Cursor 的 `~/.cursor/skills` 给编程助手用；本目录 Skills 给运行中的 MES Agent（8765/CLI）用。

横切强制策略（审计、拦截）请用 Middleware，见 [`DeepAgents-Middleware使用指南.md`](./DeepAgents-Middleware使用指南.md)。

---

## 2. 本项目已接入的方式

`apps/agent/agents/agent.py` 中：

```python
FilesystemBackend(root_dir=apps/agent, virtual_mode=True)
create_deep_agent(..., backend=backend, skills=["/skills/"])
```

含义：

- 在 `apps/agent/skills/` 下每个子目录若含 `SKILL.md`，启动时会被扫描
- Agent 启动时只注入每个 Skill 的 **name + description**（省上下文）
- 任务相关时，Agent 再通过文件系统工具读取完整 `SKILL.md`（渐进披露）
- `virtual_mode=True` 把文件访问限制在 `apps/agent` 内，降低误读仓库根 `.env` 的风险

改 Skills 或 Agent 代码后，需**重启 API**：

```bash
./scripts/stop.sh && ./scripts/dev.sh
```

---

## 3. 目录约定

```text
apps/agent/skills/
├── query-mes-data/           # 业务 Skill：查询
│   └── SKILL.md              # 必需
├── import-export-data/       # 业务 Skill：导入导出
│   └── SKILL.md
├── skill-template/           # 模板（可复制）
│   └── SKILL.md
└── your-new-skill/           # 你新建的
    ├── SKILL.md              # 必需
    ├── references/           # 可选：长文档、字段说明
    │   └── fields.md
    └── scripts/              # 可选：辅助脚本（Agent 按说明调用/阅读）
        └── check.py
```

规则：

- 目录名：小写字母、数字、连字符（如 `qc-inspect`）
- 每个 Skill **一个目录**，目录内必须有 `SKILL.md`
- 可选附属文件放同目录，在正文里写清相对路径，让 Agent 需要时再读

---

## 4. SKILL.md 格式（照抄即可）

```markdown
---
name: your-skill-name
description: >-
  一两句话说明「做什么、何时用」。
  写清触发关键词，Agent 靠这段决定要不要加载本 Skill。
---

# 标题

## 何时使用
- …

## 步骤
1. …
2. 调用 `query_platform_data(entity="...")`

## 必须用的工具
- …

## 禁止事项
- …

## 自检清单
- [ ] …
```

### frontmatter 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 唯一 id，建议与目录名一致，小写+连字符，≤64 字符 |
| `description` | 是 | **最重要**：决定会不会被选中；写场景+关键词，≤1024 字符 |
| `license` 等 | 否 | 可按 [Agent Skills 规范](https://agentskills.io/) 扩展 |

正文用 Markdown，建议包含：何时用、步骤、工具名、禁忌、自检。  
工具名必须与代码里注册的一致（见 `agents/agent.py` 的 `TOOLS`）。

---

## 5. 自己新增一个 Skill（逐步）

### 步骤 A：复制模板

```bash
cd apps/agent/skills
cp -R skill-template my-feature-name
cd my-feature-name
# 编辑 SKILL.md
```

### 步骤 B：写好 description（决定「会不会被用到」）

差的例子：

```yaml
description: 处理一些事情
```

好的例子：

```yaml
description: >-
  设备点检与故障报修时使用。用户说「点检」「报修」「设备停机」、
  查询 devices 或创建维修单时启用。
```

### 步骤 C：正文写清「调用哪个 Tool、传什么参数」

Agent 只会用已注册的 Tools。若新能力需要新 API：

1. 先在 `entities.json` 或 `tools/` 加 Tool
2. 在 `agents/agent.py` 的 `TOOLS` 注册
3. 再在 Skill 里写调用步骤

### 步骤 D：重启并验证

```bash
./scripts/stop.sh && ./scripts/dev.sh
```

在 Web 或 CLI 用**会触发 description 的话**试一轮，例如：

- 查询类 → 「查一下排程计划」
- 导入类 → 「把这个 CSV 导入工单」

### 步骤 E（可选）：加 reference

长字段表不要全塞进 `SKILL.md`，放到 `references/xxx.md`，在 Skill 里写：

```markdown
详细字段见 `references/fields.md`，需要时再读取。
```

---

## 6. 现成 Skill 一览

| 目录 | name | 用途 |
|------|------|------|
| `query-mes-data` | query-mes-data | 查工单/生产计划，防实体混用 |
| `import-export-data` | import-export-data | 预览、导入、导出、转换 |
| `skill-template` | skill-template | 复制用模板（一般不参与业务） |

---

## 7. 和 entities.json、系统提示词怎么分工

| 内容 | 放哪 |
|------|------|
| 实体 id、别名、REST path | `entities.json` |
| 全局短规则、实体清单（启动必带） | `entity_catalog.build_system_prompt()` |
| 某类业务的详细流程、禁忌、话术 | **Skill** |
| 真正的 HTTP/文件操作 | **Tool** |

经验：提示词保持短；流程一长就拆 Skill，避免所有功能挤在一个 `SYSTEM_PROMPT`。

---

## 8. 常见问题

**Q: 加了 Skill 没生效？**  
A: 是否重启了 API；目录是否在 `apps/agent/skills/<name>/SKILL.md`；`name`/`description` frontmatter 是否合法 YAML。

**Q: Agent 选错 Skill / 仍混用工单和计划？**  
A: 加强 `description` 与正文里的对照表；确认 `query-mes-data` 仍在；实体别名是否在 `entities.json`。

**Q: 要不要把 skill-template 删掉？**  
A: 可留作样板。若担心误触发，保持 description 写明「仅在用户明确要求按模板新建时参考」。

**Q: 生产环境用 FilesystemBackend 安全吗？**  
A: 已用 `virtual_mode=True` 限制在 `apps/agent`。更高安全可再加 HITL / 沙箱；勿把密钥放进 `apps/agent` 目录。

**Q: Skill 里能写 Python 让 Agent 执行吗？**  
A: 可以放 `scripts/` 作参考或由 Agent 在允许的后端里执行；默认优先用已注册 Tools，更可控。

---

## 9. 快速检查清单（发版前）

- [ ] `SKILL.md` 有合法 YAML frontmatter（`name` + `description`）
- [ ] `description` 含触发场景关键词
- [ ] 正文工具名 ∈ `TOOLS` 列表
- [ ] 需要的实体已在 `entities.json`
- [ ] 已重启 API / CLI 进程
- [ ] 用自然语言测过至少 1 条正向用例

---

## 10. 相关文件

```text
apps/agent/agents/agent.py          # create_deep_agent + skills 接入
apps/agent/skills/*/SKILL.md        # 各 Skill
apps/agent/tools/                   # Tools
apps/agent/tools/query_tool/entities.json
docs/平台查询工具维护笔记.md         # 实体/查询维护
docs/DeepAgents-Skills使用指南.md    # 本文
```
