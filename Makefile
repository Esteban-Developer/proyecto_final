SHELL := /bin/bash

COMPOSE_FILE := fastapi_app/docker-compose.yml

.PHONY: help start up stop down restart logs rebuild ps api worker

help:
	@echo "Comandos disponibles:"
	@echo "  make start / up   -> levanta API + Worker + Redis + RabbitMQ + Portainer"
	@echo "  make stop / down  -> detiene contenedores"
	@echo "  make restart      -> reinicia el stack"
	@echo "  make logs    -> muestra logs de todos los servicios"
	@echo "  make rebuild -> reconstruye imágenes y levanta"
	@echo "  make ps      -> estado de contenedores"
	@echo "  make api     -> logs de API"
	@echo "  make worker  -> logs de worker"

start:
	docker compose -f $(COMPOSE_FILE) up -d

up: start

stop:
	docker compose -f $(COMPOSE_FILE) down

down: stop

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

