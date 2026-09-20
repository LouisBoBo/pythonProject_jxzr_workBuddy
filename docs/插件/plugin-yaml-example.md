# plugin.yaml 清单模板

复制以下内容到 `plugins/<id>/plugin.yaml` 并填写。

```yaml
# 必填
id: example-plugin              # 全局唯一：小写 + 连字符
version: 0.0.0                  # semver
name: 示例插件                   # 插件中心展示名（中文）
features: ["00"]                # 对应 docs/功能实现 编号

depends_on:
  - kernel                      # 必填；可选 mes-profile 等

agent:
  tools_module: agent.tools
  skills_dirs:
    - agent/skills
  lane_prompts_module: null     # 可选
  lanes: []                     # code_dev / code_review / paste_code

api:
  router: api.routes:router
  prefix: /api/p/example-plugin
  legacy_prefixes: []
  tags:
    - 示例

web:
  entry: web/dist/client.js
  sidebar: []                   # { label, path, icon }

lifecycle:
  module: api.lifecycle

integrity:
  sha256: ""

capabilities:
  - chat.tools
  - chat.skills
  # - api.routes
  # - web.routes
  # - scheduler
```

字段说明见 [架构设计方案.md §4](./架构设计方案.md#4-插件契约pluginyaml)。
