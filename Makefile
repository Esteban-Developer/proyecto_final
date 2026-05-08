SHELL := /bin/bash

COMPOSE_FILE := fastapi_app/docker-compose.yml

.PHONY: help start stop restart logs rebuild ps api worker

help:
	@echo "Comandos disponibles:"
	@echo "  make start   -> levanta API + Worker + Redis + RabbitMQ"
	@echo "  make stop    -> detiene contenedores"
	@echo "  make restart -> reinicia el stack"
	@echo "  make logs    -> muestra logs de todos los servicios"
	@echo "  make rebuild -> reconstruye imágenes y levanta"
	@echo "  make ps      -> estado de contenedores"
	@echo "  make api     -> logs de API"
	@echo "  make worker  -> logs de worker"

start:
	docker compose -f $(COMPOSE_FILE) up -d

stop:
	docker compose -f $(COMPOSE_FILE) down

restart: stop start

logs:
	docker compose -f $(COMPOSE_FILE) logs -f --tail=200

rebuild:
	docker compose -f $(COMPOSE_FILE) up -d --build

ps:
	docker compose -f $(COMPOSE_FILE) ps

api:
	docker compose -f $(COMPOSE_FILE) logs -f --tail=200 api

worker:
	docker compose -f $(COMPOSE_FILE) logs -f --tail=200 worker

