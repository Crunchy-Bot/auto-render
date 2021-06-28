import asyncio
import uuid

from typing import Dict
from fastapi import WebSocket


class RenderWorker:
    def __init__(self, ws: WebSocket):
        self.tag = uuid.uuid4()
        self.events = asyncio.Queue()
        self.handles: Dict[str, asyncio.Future] = {}
        self.ws = ws

    def __eq__(self, other):
        return other == self.tag

    def __hash__(self):
        return hash(self.tag)

    async def handle_reader(self):
        try:
            while True:
                msg = await self.ws.receive_json()
                render_id = msg['id']
                render = msg['render']
                fut = self.handles.pop(render_id)
                fut.set_result(render)
        except:
            return

    async def handle_writes(self):
        try:
            while True:
                render_id, fut = await self.events.get()
                self.handles[str(render_id)] = fut
                await self.ws.send_json({"id": str(render_id)})
        except:
            return

