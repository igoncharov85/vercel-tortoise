import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from tortoise import fields, Tortoise
from tortoise.models import Model
from tortoise.contrib.fastapi import register_tortoise

logger = logging.getLogger(__name__)
load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL_NO_SSL")
SENTRY_DSN = os.getenv("SENTRY_DSN")
VERCEL_TARGET_ENV = os.getenv("VERCEL_TARGET_ENV", "LOCAL_RUN")

TORTOISE_CONFIG = {
    "connections": {"default": DATABASE_URL},
    "apps": {
        "models": {
            "models": ["app"],
            "default_connection": "default",
        },
    },
    "use_tz": False,
    "timezone": "UTC"
}


def register_orm(fast_app: FastAPI):
    register_tortoise(
            fast_app,
            TORTOISE_CONFIG,
            generate_schemas=True,
            add_exception_handlers=True,
        )


@asynccontextmanager
async def lifespan(fast_api_app: FastAPI) -> AsyncGenerator[None, None]:
    # app startup
    register_orm(fast_api_app)
    yield
    # db connections closed
    await Tortoise.close_connections()

app = FastAPI(lifespan=lifespan, docs_url="/")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=True,
        traces_sample_rate=0,
        environment=VERCEL_TARGET_ENV
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Vercel is not able to process db request without it
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    await Tortoise.init(TORTOISE_CONFIG)
    try:
        response = await call_next(request)
    except Exception as ex:
        logger.exception(ex)
        return Response("Internal server error", status_code=500)
    finally:
        await Tortoise.close_connections()
    return response


@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as ex:
        logger.exception(ex)
        return Response("Internal server error", status_code=500)


class PingHistory(Model):
    Id = fields.IntField(pk=True)
    IPAddress = fields.CharField(max_length=50, null=True)
    CreatedAt = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "PingHistory"


class PingRequest(BaseModel):
    SaveAsync: bool = True


@app.post("/ping")
async def ping(fast_request: Request, request: PingRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(save_ping_history, request.SaveAsync, fast_request.client.host)
    return {"message": "pong!"}


async def save_ping_history(save_async: bool, ip_address):
    logger.warning("Starting to save Ping History")
    if save_async:
        await PingHistory.create(IPAddress=ip_address)
    logger.warning("Saved Ping History")


@app.get("/history")
async def ping_history(request_obj: Request):
    history = await PingHistory.filter(IPAddress=request_obj.client.host).order_by("-CreatedAt").offset(0).limit(20)
    data = [{"Id": item.Id, "IPAddress": item.IPAddress, "CreatedAt": item.CreatedAt} for item in history]
    return {"data": data}
