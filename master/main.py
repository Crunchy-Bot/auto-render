import asyncio
import sqlite3
import uuid
import os
import httpx
import logging
import json

from typing import Dict
from pydantic import UUID4, BaseModel
from collections import deque

from fastapi import FastAPI, WebSocket, Body
from fastapi.responses import JSONResponse, HTMLResponse
from jinja2 import Environment, DictLoader
from jinja2.exceptions import TemplateNotFound

from workers import RenderWorker

logger = logging.getLogger("render-master")
logging.basicConfig(level=logging.INFO)


LUST_ADMIN_URL = os.getenv("LUST_ADMIN_HOST")
LUST_URL = os.getenv("LUST_HOST")


if __name__ != '__main__':
    connection = sqlite3.connect("templates.db")
    cur = connection.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS templates (id TEXT PRIMARY KEY, html TEXT)")
    connection.commit()

    data = cur.execute("SELECT * FROM templates").fetchall()
    cur.close()

    render_templates = {row[0]: row[1] for row in data}
    templates = Environment(
        loader=DictLoader(render_templates),
        enable_async=True,
    )


class CustomFastApi(FastAPI):
    def __init__(self, **extra):
        super().__init__(**extra)

        self.workers = deque([])
        self.rendered: Dict[uuid.UUID, str] = {}
        self.session = httpx.AsyncClient(http2=True)


app = CustomFastApi(
    redoc_url="/",
    docs_url=None,
)


@app.websocket("/worker")
async def worker_connect(websocket: WebSocket):
    await websocket.accept()

    ws_handle = RenderWorker(websocket)
    app.workers.append(ws_handle)
    asyncio.create_task(ws_handle.handle_reader())
    await ws_handle.handle_writes()
    app.workers.remove(ws_handle)


class TemplateResponse(BaseModel):
    template: str
    message: str


@app.post("/templates", response_model=TemplateResponse)
async def add_template(template_id: str = Body(...), template: str = Body(...)):
    render_templates[template_id] = template

    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO templates (id, html) 
        VALUES(?, ?) 
        ON CONFLICT (id)
        DO UPDATE 
        SET html = excluded.html
        """,
        (template_id, template)
    )
    connection.commit()

    return TemplateResponse(template=template_id, message="template added")


@app.delete("/templates", response_model=TemplateResponse)
async def remove_template(template_id: str):
    try:
        del render_templates[template_id]
    except KeyError:
        return JSONResponse({"template": template_id, "message": "template not found"}, status_code=404)

    cursor = connection.cursor()
    cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    connection.commit()

    return TemplateResponse(template=template_id, message="template deleted")


class RenderResponse(BaseModel):
    template: str
    render: str


@app.post("/render/{template_id:str}", responses={404: {"model": TemplateResponse}})
async def render_template(template_id: str, context: dict = Body(...)):
    logger.info(f"rendering template: {template_id} with context: {context!r}")
    try:
        template = templates.get_template(template_id)
    except TemplateNotFound:
        return JSONResponse({"template": template_id, "message": "not found"}, status_code=404)

    rendered_html = await template.render_async(**context)
    logger.debug(f"rendered: {rendered_html}")
    render_id = uuid.uuid4()
    app.rendered[render_id] = rendered_html

    loop = asyncio.get_running_loop()
    fut = loop.create_future()

    worker = app.workers[0]
    app.workers.rotate(1)
    worker.events.put_nowait((render_id, fut))

    response = await fut
    del app.rendered[render_id]

    if response is None:
        return JSONResponse({"template": template_id, "message": "no render id in html"}, status_code=400)

    payload = {
        "format": "png",
        "data": response,
        "category": template_id
    }
    r = await app.session.post(f"{LUST_ADMIN_URL}/admin/create/image", json=payload)
    r.raise_for_status()

    r_data = json.loads(await r.aread())
    file_id = r_data['data']['file_id']

    return RenderResponse(
        template=template_id,
        render=f"{LUST_URL}/{template_id}/{file_id}",
    )


@app.get("/rendered/{render_id:uuid}")
async def get_rendered(render_id: UUID4):
    rendered_html = app.rendered[render_id]
    return HTMLResponse(rendered_html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)