import asyncio
import threading
import tkinter as tk
import websockets

SERVER = "wss://shout-server-production.up.railway.app"

class TeacherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("办公室喊话")
        self.root.geometry("450x350")

        tk.Label(self.root, text="喊话内容：", font=("微软雅黑", 12)).pack(pady=8)
        self.msg = tk.Text(self.root, height=7, font=("微软雅黑", 13))
        self.msg.pack(fill="x", padx=12)

        tk.Button(self.root, text="发送喊话", font=("微软雅黑", 13),
                  bg="#4CAF50", fg="white", command=self.send).pack(pady=12)

        self.status = tk.Label(self.root, text="正在连接服务器...", fg="orange",
                               font=("微软雅黑", 10))
        self.status.pack()

        self.ws = None
        self.loop = None
        threading.Thread(target=self.connect, daemon=True).start()
        self.root.mainloop()

    def connect(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def _conn():
            while True:
                try:
                    async with websockets.connect(SERVER) as ws:
                        await ws.send("ROLE:teacher")
                        self.ws = ws
                        self.status.config(text="已连接，可以喊话", fg="green")
                        await asyncio.Future()
                except Exception:
                    self.ws = None
                    self.status.config(text="连接断开，重试中...", fg="red")
                    await asyncio.sleep(3)

        self.loop.run_until_complete(_conn())

    def send(self):
        if not self.ws:
            self.status.config(text="未连接，无法发送", fg="red")
            return
        text = self.msg.get("1.0", "end").strip()
        if not text:
            return
        asyncio.run_coroutine_threadsafe(self.ws.send(text), self.loop)
        self.msg.delete("1.0", "end")

if __name__ == "__main__":
    TeacherApp()
