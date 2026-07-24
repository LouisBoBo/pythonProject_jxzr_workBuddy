.PHONY: install install-web dev stop api web agent-cli health

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
