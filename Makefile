.PHONY: up down restart logs ps passwd

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

# Usage: make passwd PASS=your-chosen-password
passwd:
	@./scripts/gen_password.sh "$(PASS)"
