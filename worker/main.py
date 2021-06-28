import asyncio
import aiohttp
import time
import logging

from selenium import webdriver
from selenium.webdriver.firefox import options

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

logger = logging.getLogger("render-engine")
logging.basicConfig(level=logging.INFO)

target_url = "http://auto-render:8000/rendered/{}"

options = options.Options()
options.headless = True
driver = webdriver.Firefox(options=options)


def get_html(render_id):
    start = time.perf_counter()
    driver.get(target_url.format(render_id))
    resp = driver.find_element_by_tag_name("body").screenshot_as_base64
    stop = time.perf_counter() - start
    logger.info(f"render took {stop * 1000}ms to render")
    return resp


async def main():
    loop = asyncio.get_running_loop()
    async with aiohttp.ClientSession() as sess:
        ws = await sess.ws_connect("ws://auto-render:8000/worker")
        while not ws.closed:
            msg = await ws.receive_json()
            render_id = msg['id']
            bs64 = await loop.run_in_executor(None, get_html, render_id)
            data = {
                "id": render_id,
                "render": bs64
            }
            await ws.send_json(data)

if __name__ == "__main__":
    asyncio.run(main())
