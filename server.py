import asyncio
import json
import os
import websockets

GRADES = ["高一", "高二", "高三"]
CLASS_NUMS = list(range(1, 17))

def all_rooms():
    rooms = []
    for g in GRADES:
        for n in CLASS_NUMS:
            rooms.append({"room_id": f"{g}{n}班", "name": f"{g}{n}班"})
    return rooms

ROOMS = {r["room_id"]: r for r in all_rooms()}

teachers_online = {}
rooms_online = {}

async def send_json(ws, obj):
    try:
        await ws.send(json.dumps(obj, ensure_ascii=False))
    except Exception:
        pass

def online_room_ids():
    return list(set(info["room_id"] for info in rooms_online.values()))

async def broadcast_room_status():
    ids = online_room_ids()
    for tws in list(teachers_online.keys()):
        await send_json(tws, {"type": "room_status", "online": ids})

async def handler(ws):
    role = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            action = msg.get("action")

            if action == "teacher_login":
                username = msg.get("username", "").strip() or "老师"
                role = "teacher"
                teachers_online[ws] = {"username": username}
                await send_json(ws, {
                    "type": "login_ok",
                    "username": username,
                    "rooms": list(ROOMS.values())
                })
                await send_json(ws, {
                    "type": "room_status",
                    "online": online_room_ids()
                })

            elif action == "shout":
                if ws not in teachers_online:
                    continue
                room_ids = msg.get("room_ids", [])
                text = msg.get("text", "").strip()
                show_sender = bool(msg.get("show_sender", False))
                if not text or not room_ids:
                    continue
                sender = teachers_online[ws]["username"]
                payload = {
                    "type": "shout",
                    "text": text,
                    "sender": sender if show_sender else "",
                }
                sent = 0
                for rws, info in list(rooms_online.items()):
                    if info["room_id"] in room_ids:
                        await send_json(rws, payload)
                        sent += 1
                await send_json(ws, {"type": "sent", "count": sent})

            elif action == "room_hello":
                room_id = msg.get("room_id", "").strip()
                if room_id not in ROOMS:
                    await send_json(ws, {"type": "error", "msg": f"未知班级：{room_id}"})
                    continue
                role = "room"
                rooms_online[ws] = {"room_id": room_id}
                await send_json(ws, {
                    "type": "room_ok",
                    "room_id": room_id,
                    "name": room_id
                })
                await broadcast_room_status()

    except websockets.ConnectionClosed:
        pass
    finally:
        if ws in teachers_online:
            del teachers_online[ws]
        if ws in rooms_online:
            del rooms_online[ws]
            await broadcast_room_status()

async def main():
    port = int(os.environ.get("PORT", 8080))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"服务器启动，端口 {port}")
        await asyncio.Future()

asyncio.run(main())
