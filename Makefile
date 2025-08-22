.PHONY: build up down logs migrate update

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f web

migrate:
	docker-compose exec web alembic upgrade head

update: down build up migrate