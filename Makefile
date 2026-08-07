.PHONY: install install-web dev stop api web agent-cli health smoke-api-health smoke-entity-phrases smoke-embed-identity smoke-ha smoke-ide-review-m0 smoke-ide-bridge-m1 smoke-checkpoint-context smoke-api-contracts package-vscode-bridge check-cursor-dev smoke-cursor-dev

install:
	python3 -m pip install -r requirements.txt

install-web:
	cd apps/web && npm install

dev:
	./scripts/dev.sh

stop:
	./scripts/stop.sh

api:
	cd apps/api && python3 main.py

web:
	cd apps/web && npm run dev -- --host 0.0.0.0 --port 5180 --strictPort

agent-cli:
	python3 apps/agent/run.py cli

health:
	@curl -sf http://127.0.0.1:8765/health | python3 -m json.tool

# 无 LLM：日志分析必跑；探活需 8081+8001（不可用则 SKIP）
# 强制探活：SMOKE_REQUIRE_PROBE=1 make smoke-api-health
smoke-api-health:
	python3 scripts/smoke_api_health.py

# 无 LLM：实体别名解析 + 实体守卫双向规则
smoke-entity-phrases:
	python3 scripts/smoke_entity_phrases.py

# 无 LLM：嵌入身份 / 历史隔离 / 页上下文前缀
smoke-embed-identity:
	python3 scripts/smoke_embed_identity.py

# 无 LLM：跨进程锁 + 双实例抢确认 CAS
smoke-ha:
	python3 scripts/smoke_ha.py

# 无 LLM：M0 IDE 审核（默认 mock 必过；可选 IDE_REVIEW_MCP=1 试本机 MCP）
smoke-ide-review-m0:
	python3 scripts/smoke_ide_review_m0.py

# 无 LLM：M1 Bridge 注册/投递/回传闭环
smoke-ide-bridge-m1:
	python3 scripts/smoke_ide_bridge_m1.py

# 无 LLM：会话 checkpointer / 历史回填
smoke-checkpoint-context:
	python3 scripts/smoke_checkpoint_context.py

# 需本机 API：HTTP 契约（health/历史隔离/上传/SSE 开流）
smoke-api-contracts:
	python3 scripts/smoke_api_contracts.py

# 打包 VS Code Bridge 为 dist/*.vsix
package-vscode-bridge:
	bash scripts/package_vscode_bridge.sh

# Cursor 写码车道：管理员就绪闸门（读 .env，可无 LLM）
check-cursor-dev:
	python3 scripts/check_cursor_dev_ready.py

# Cursor 写码旁路单元/流程冒烟（D5：摘要去重、merge_guide 等）
smoke-cursor-dev:
	python3 scripts/smoke_cursor_dev_d5.py
