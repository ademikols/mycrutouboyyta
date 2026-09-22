import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, WebAppInfo, InlineKeyboardMarkup

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
PORT = int(os.getenv("PORT", 8080))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

rooms = {}

@app.get("/")
async def index():
    with open("public/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/health")
async def health():
    return {"ok": True}

@app.websocket("/ws/{room_id}")
async def ws_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    room = rooms.setdefault(room_id, {
        "clients": set(),
        "state": {"video_url": "", "time": 0, "is_playing": False}
    })
    room["clients"].add(websocket)
    await websocket.send_json({"type": "state", "state": room["state"]})
    try:
        while True:
            data = await websocket.receive_json()
            t = data.get("type")
            if t == "set_video":
                room["state"]["video_url"] = data.get("url", "")
                room["state"]["time"] = 0
                room["state"]["is_playing"] = False
            elif t == "play":
                room["state"]["is_playing"] = True
                room["state"]["time"] = data.get("time", 0)
            elif t == "pause":
                room["state"]["is_playing"] = False
                room["state"]["time"] = data.get("time", 0)
            elif t == "seek":
                room["state"]["time"] = data.get("time", 0)
            for c in list(room["clients"]):
                if c is websocket:
                    continue
                try:
                    await c.send_json(data)
                except Exception:
                    room["clients"].discard(c)
    except WebSocketDisconnect:
        room["clients"].discard(websocket)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎬 Смотреть вместе",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/?room={message.chat.id}")
        )]
    ])
    await message.answer("Жми кнопку чтобы открыть комнату 👇", reply_markup=kb)

async def run_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

async def run_server():
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(run_bot(), run_server())

if __name__ == "__main__":
    asyncio.run(main())
