# zimuzo backend

## Overview
This backend application is built using FastAPI. It provides a RESTful API for managing resources.

## Requirements
- Python 3.10+
- FastAPI
- Uvicorn
- UV

If you have docker desktop installed locally, then run command `docker-compose up`. This command sets up database, application and pgadmin for the database.

Useful commands if you want to run locally:

```
To run makemigrations and apply migrations

docker-compose exec app uv run alembic revision --autogenerate -m
docker-compose exec app uv run alembic upgrade head

```
