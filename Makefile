.PHONY: install install-web dev stop api web agent-cli health smoke-api-health smoke-entity-phrases smoke-embed-identity smoke-ha

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
