# 回滚说明 · Cursor 写码提速（2026-08-10）

本目录为改动前快照。回滚任选其一。

## 方式 A：从本备份覆盖

```bash
ROOT="/Users/hebo/WorkBuddy/2026-07-23-09-13-55/simplified-workbuddy"
B="$ROOT/docs/备份/cursor-dev-speed-2026-08-10"
cp -p "$B/prompts.py" "$ROOT/apps/cursor_dev/prompts.py"
cp -p "$B/project_inspect.py" "$ROOT/apps/cursor_dev/project_inspect.py"
cp -p "$B/cursor_dev.py" "$ROOT/apps/api/routes/cursor_dev.py"
cp -p "$B/SKILL.md" "$ROOT/apps/agent/skills/cursor-dev-chat/SKILL.md"
cp -p "$B/ChatView.vue" "$ROOT/apps/web/src/views/ChatView.vue"
```

然后重启 API；前端刷新即可。

## 方式 B：Git（未提交提速改动时）

```bash
git checkout -- \
  apps/cursor_dev/prompts.py \
  apps/cursor_dev/project_inspect.py \
  apps/api/routes/cursor_dev.py \
  apps/agent/skills/cursor-dev-chat/SKILL.md \
  apps/web/src/views/ChatView.vue
```
