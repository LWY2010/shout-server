import asyncio
import os
import websockets

clients = {"teacher": set(), "screen": set()}

async def handler(ws):
    role = None
    try:
        async for msg in ws:
            if msg.startswith("ROLE:"):
                role = msg.split(":")[1]
                clients[role].add(ws)
                print(f"[+] {role} 已连接，当前大屏数：{len(clients['screen'])}")
                continue
            if role == "teacher":
                print(f"[喊话] {msg}")
                for screen in list(clients["screen"]):
                    try:
                        await screen.send(msg)
                    except Exception:
                        clients["screen"].discard(screen)
    finally:
        if role:
            clients[role].discard(ws)
            print(f"[-] {role} 断开")

async def main():
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"服务器启动，监听端口 {port}")
        await asyncio.Future()

asyncio.run(main())
