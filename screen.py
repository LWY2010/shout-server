import asyncio
import threading
import tkinter as tk
import websockets
import win32com.client

SERVER = "wss://shout-server-production.up.railway.app"

speaker = win32com.client.Dispatch("SAPI.SpVoice")

class ScreenApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("班级大屏")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="black")
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        self.label = tk.Label(
            self.root, text="等待喊话...", font=("微软雅黑", 72, "bold"),
            fg="white", bg="black", wraplength=1700, justify="center"
        )
        self.label.pack(expand=True)

        self.status = tk.Label(self.root, text="连接中...", font=("微软雅黑", 16),
                               fg="gray", bg="black")
        self.status.pack(side="bottom", pady=10)

        threading.Thread(target=self.listen, daemon=True).start()
        self.root.mainloop()

    def listen(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _listen():
            while True:
                try:
                    async with websockets.connect(SERVER) as ws:
                        await ws.send("ROLE:screen")
                        self.root.after(0, lambda: self.status.config(
                            text="已连接", fg="green"))
                        async for msg in ws:
                            self.root.after(0, lambda m=msg: self.show(m))
                except Exception:
                    self.root.after(0, lambda: self.status.config(
                        text="连接断开，重试中...", fg="red"))
                    await asyncio.sleep(3)

        loop.run_until_complete(_listen())

    def show(self, text):
        self.label.config(text=text, fg="yellow")
        threading.Thread(target=lambda: speaker.Speak(text), daemon=True).start()
        self.root.after(8000, lambda: self.label.config(text="", fg="white"))

if __name__ == "__main__":
    ScreenApp()
