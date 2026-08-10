# 回滚 P0/P1/P2（2026-08-10）

```bash
ROOT="/Users/hebo/WorkBuddy/2026-07-23-09-13-55/simplified-workbuddy"
B="$ROOT/docs/备份/cursor-dev-p0p1p2-2026-08-10"
cp -p "$B/service.py" "$ROOT/apps/cursor_dev/service.py"
cp -p "$B/jobs.py" "$ROOT/apps/cursor_dev/jobs.py"
cp -p "$B/prompts.py" "$ROOT/apps/cursor_dev/prompts.py"
cp -p "$B/project_inspect.py" "$ROOT/apps/cursor_dev/project_inspect.py"
cp -p "$B/cursor_dev.py" "$ROOT/apps/api/routes/cursor_dev.py"
cp -p "$B/ChatView.vue" "$ROOT/apps/web/src/views/ChatView.vue"
# 新增文件可删（不影响回滚后运行）
rm -f "$ROOT/apps/cursor_dev/repo_index.py" "$ROOT/apps/cursor_dev/patch_channel.py"
```

然后重启 API。
