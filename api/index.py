from fastapi import FastAPI, Request, BackgroundTasks
from tortoise import fields
from tortoise.models import Model

from api.initializer import init

app = FastAPI(docs_url="/")

init(app)


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
