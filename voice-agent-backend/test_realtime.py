import os
import json
import base64
import asyncio
import websockets
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
URL = f"wss://api.openai.com/v1/realtime?model={MODEL}"

async def main():
    async with websockets.connect(
        URL,
        additional_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        },
    ) as ws:
        # 1) Configure session for text (no audio)
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text"],
                "instructions": "You are a test assistant. Answer very briefly.",
            },
        }))

        # 2) Create a simple text response
        await ws.send(json.dumps({
            "type": "response.create",
            "response": {
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "output_text", "text": "Say hello in one word."}
                        ]
                    }
                ],
                "modalities": ["text"],
            },
        }))

        async for msg in ws:
            event = json.loads(msg)
            print("EVENT:", event["type"])
            if event["type"] == "response.output_text.delta":
                print("TEXT DELTA:", event["delta"]["text"])
            if event["type"] == "response.output_text.done":
                print("DONE.")
                break

asyncio.run(main())
