DOCKER_COMPOSE := $(shell command -v docker-compose 2> /dev/null || echo "docker compose")

.PHONY: up down logs restart api-shell api-worker-shell postgres-shell neo4j-shell web-shell

up:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml up -d --build && \
	(echo "" && echo "BUILD STATUS: SUCCESS" && echo "OPEN NOW:" && echo "http://localhost:3000")

down:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml down

logs:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml logs -f

restart:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml down -v
	$(MAKE) up

api-shell:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml exec api bash

api-worker-shell:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml exec worker bash

postgres-shell:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml exec postgres psql -U repobrain -d repobrain

neo4j-shell:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml exec neo4j cypher-shell -u neo4j -p repobrainneo4j

web-shell:
	$(DOCKER_COMPOSE) -f infra/compose/docker-compose.dev.yml exec web sh