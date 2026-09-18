.PHONY: up down logs seed test lint fresh

up:            ## build and start the whole stack
	docker compose up -d --build

down:
	docker compose down

fresh:         ## wipe the database volume and start clean
	docker compose down -v && docker compose up -d --build

logs:
	docker compose logs -f api

seed:          ## (re)load the sample workbook data
	docker compose run --rm seed

test:
	cd backend && DATABASE_URL=sqlite:///./test.db python -m pytest -q

lint:
	cd backend && ruff check app tests
