import asyncio

from typing import Dict
from fastapi import WebSocket


class RenderWorker:
    def __init__(self, ws: WebSocket):
        self.events = asyncio.Queue()
        self.handles: Dict[str, asyncio.Future] = {}
        self.ws = ws

    async def handle_reader(self):
        while True:
            msg = await self.ws.receive_json()
            render_id = msg['id']
            render = msg['render']
            fut = self.handles.pop(render_id)
            fut.set_result(render)

    async def handle_writes(self):
        while True:
            render_id, fut = await self.events.get()
            self.handles[str(render_id)] = fut
            await self.ws.send_json({"id": str(render_id)})
