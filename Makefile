.PHONY: up down logs restart api-shell api-worker-shell postgres-shell neo4j-shell web-shell

up:
	docker compose -f infra/compose/docker-compose.dev.yml up -d --build && \
	(echo "" && echo "BUILD STATUS: SUCCESS" && echo "OPEN NOW:" && echo "http://localhost:3000")

down:
	docker compose -f infra/compose/docker-compose.dev.yml down

logs:
	docker compose -f infra/compose/docker-compose.dev.yml logs -f

restart:
	docker compose -f infra/compose/docker-compose.dev.yml down -v
	$(MAKE) up

api-shell:
	docker compose -f infra/compose/docker-compose.dev.yml exec api bash

api-worker-shell:
	docker compose -f infra/compose/docker-compose.dev.yml exec worker bash

postgres-shell:
	docker compose -f infra/compose/docker-compose.dev.yml exec postgres psql -U repobrain -d repobrain

neo4j-shell:
	docker compose -f infra/compose/docker-compose.dev.yml exec neo4j cypher-shell -u neo4j -p repobrainneo4j

web-shell:
	docker compose -f infra/compose/docker-compose.dev.yml exec web sh