import sys
import asyncio
from pathlib import Path

sys.path.insert(0, r"d:\Rogius\src\tui")
sys.path.insert(0, r"d:\Rogius\src")

from api_server import _get_main_agent

async def run():
    agent = _get_main_agent()
    async for event in agent.execute_streaming("Open google.com, search for hello world, and take a screenshot", max_retries=1):
        print(event)

if __name__ == "__main__":
    asyncio.run(run())
