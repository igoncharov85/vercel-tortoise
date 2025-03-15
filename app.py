import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from starlette.middleware.cors import CORSMiddleware
from tortoise import fields, Tortoise
from tortoise.models import Model
from tortoise.contrib.fastapi import register_tortoise

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL_NO_SSL")

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

app = FastAPI(docs_url="/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await Tortoise.init(TORTOISE_CONFIG)


@app.on_event("shutdown")
async def shutdown_event():
    await Tortoise.close_connections()


register_tortoise(
        app,
        TORTOISE_CONFIG,
        generate_schemas=True,
        add_exception_handlers=True,
    )

# Vercel is not able to process db request without it
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    await Tortoise.init(TORTOISE_CONFIG)
    response = await call_next(request)
    await Tortoise.close_connections()
    return response


class PingHistory(Model):
    Id = fields.IntField(pk=True)
    IPAddress = fields.CharField(max_length=50, null=True)
    CreatedAt = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "PingHistory"


@app.get("/ping")
async def ping(request_obj: Request, background_tasks: BackgroundTasks):
    background_tasks.add_task(save_ping_history, request_obj.client.host)
    return {"message": "pong!"}


async def save_ping_history(ip_address):
    await PingHistory.create(IPAddress=ip_address)


@app.get("/history")
async def ping_history(request_obj: Request):
    history = await PingHistory.filter(IPAddress=request_obj.client.host).order_by("-CreatedAt").offset(0).limit(20)
    data = [{"Id": item.Id, "IPAddress": item.IPAddress, "CreatedAt": item.CreatedAt} for item in history]
    return {"data": data}
