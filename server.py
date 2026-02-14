import json
import string
import random
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import database as db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

WEBAPP_DIR = Path(__file__).parent / "webapp"


# ─── Room Manager ───
class RoomManager:
    def __init__(self):
        self.connections: dict[str, list[dict]] = {}

    async def connect(self, room_code: str, ws: WebSocket, user_info: dict):
        await ws.accept()
        if room_code not in self.connections:
            self.connections[room_code] = []
        self.connections[room_code].append({"ws": ws, "user": user_info})
        await self.broadcast(room_code, {
            "type": "user_joined",
            "user": user_info,
            "members": self.count(room_code),
        })

    def disconnect(self, room_code: str, ws: WebSocket):
        if room_code in self.connections:
            user_info = None
            for c in self.connections[room_code]:
                if c["ws"] is ws:
                    user_info = c["user"]
            self.connections[room_code] = [c for c in self.connections[room_code] if c["ws"] is not ws]
            if not self.connections[room_code]:
                del self.connections[room_code]
            return user_info
        return None

    def count(self, room_code: str) -> int:
        return len(self.connections.get(room_code, []))

    def members(self, room_code: str) -> list[dict]:
        return [c["user"] for c in self.connections.get(room_code, [])]

    async def broadcast(self, room_code: str, message: dict, exclude: WebSocket | None = None):
        if room_code in self.connections:
            dead = []
            for c in self.connections[room_code]:
                if c["ws"] is not exclude:
                    try:
                        await c["ws"].send_json(message)
                    except Exception:
                        dead.append(c["ws"])
            for ws in dead:
                self.disconnect(room_code, ws)


manager = RoomManager()


def gen_code(length=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


# ─── Serve webapp ───
@app.get("/")
async def serve_index():
    return FileResponse(WEBAPP_DIR / "index.html")


# ─── API ───
@app.post("/api/users")
async def api_create_user(data: dict):
    await db.upsert_user(data["telegram_id"], data.get("username", ""), data.get("first_name", ""))
    return {"ok": True}


@app.get("/api/users/{telegram_id}")
async def api_get_user(telegram_id: int):
    user = await db.get_user(telegram_id)
    if not user:
        return JSONResponse({"error": "not found"}, 404)
    return dict(user)


@app.post("/api/rooms")
async def api_create_room(data: dict):
    code = gen_code()
    await db.create_room(
        code, data.get("name", "Комната"), data["creator_id"],
        data.get("video_url", ""), data.get("video_title", ""),
    )
    return {"ok": True, "code": code}


@app.get("/api/rooms")
async def api_list_rooms():
    rooms = await db.get_active_rooms()
    result = []
    for r in rooms:
        d = dict(r)
        d["members_online"] = manager.count(d["code"])
        result.append(d)
    return result


@app.get("/api/rooms/{code}")
async def api_get_room(code: str):
    room = await db.get_room(code)
    if not room:
        return JSONResponse({"error": "not found"}, 404)
    d = dict(room)
    d["members_online"] = manager.count(code)
    d["members"] = manager.members(code)
    return d


@app.delete("/api/rooms/{code}")
async def api_close_room(code: str):
    await db.close_room(code)
    await manager.broadcast(code, {"type": "room_closed"})
    return {"ok": True}


@app.get("/api/rooms/{code}/messages")
async def api_get_messages(code: str):
    msgs = await db.get_messages(code)
    return [dict(m) for m in msgs]


@app.post("/api/users/{telegram_id}/watch")
async def api_add_watch_time(telegram_id: int, data: dict):
    seconds = data.get("seconds", 0)
    if seconds > 0:
        await db.update_user_stat(telegram_id, "total_watch_time", seconds)
    return {"ok": True}


@app.post("/api/users/{telegram_id}/movie")
async def api_movie_watched(telegram_id: int):
    await db.update_user_stat(telegram_id, "movies_watched", 1)
    return {"ok": True}


# ─── WebSocket ───
@app.websocket("/ws/{room_code}")
async def ws_endpoint(
    websocket: WebSocket,
    room_code: str,
    user_id: int = Query(0),
    username: str = Query(""),
    first_name: str = Query(""),
):
    user_info = {"id": user_id, "username": username, "first_name": first_name or username}
    room = await db.get_room(room_code)
    if not room:
        await websocket.close(code=4004)
        return

    await manager.connect(room_code, websocket, user_info)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "chat":
                text = data.get("text", "").strip()
                if text:
                    await db.save_message(room_code, user_id, user_info["first_name"], text)
                    await db.update_user_stat(user_id, "messages_sent", 1)
                    await manager.broadcast(room_code, {
                        "type": "chat",
                        "user": user_info,
                        "text": text,
                        "ts": int(time.time()),
                    })

            elif msg_type in ("play", "pause", "seek", "sync"):
                await manager.broadcast(room_code, {
                    "type": msg_type,
                    "time": data.get("time", 0),
                    "user": user_info,
                }, exclude=websocket)

            elif msg_type == "reaction":
                await manager.broadcast(room_code, {
                    "type": "reaction",
                    "emoji": data.get("emoji", "👍"),
                    "user": user_info,
                })

            elif msg_type == "get_members":
                await websocket.send_json({
                    "type": "members",
                    "list": manager.members(room_code),
                    "count": manager.count(room_code),
                })

    except WebSocketDisconnect:
        left_user = manager.disconnect(room_code, websocket)
        if left_user:
            await manager.broadcast(room_code, {
                "type": "user_left",
                "user": left_user,
                "members": manager.count(room_code),
            })
    except Exception:
        manager.disconnect(room_code, websocket)