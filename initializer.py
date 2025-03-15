import os

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL_NO_SSL")

TORTOISE_CONFIG = {
    "connections": {"default": DATABASE_URL},
    "apps": {
        "models": {
            "models": ["db"],
            "default_connection": "default",
        },
    },
    "use_tz": False,
    "timezone": "UTC"
}


def init(app: FastAPI):
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db(app)


async def close_db_connections():
    """Close database connections when application shuts down"""
    await Tortoise.close_connections()


def init_db(app: FastAPI):
    register_tortoise(
        app,
        db_url=DATABASE_URL,
        modules={"models": ["api.index"]},
        generate_schemas=True,
        add_exception_handlers=True,
    )

    # Add event handler for application shutdown
    app.add_event_handler("shutdown", close_db_connections)
