import asyncio
import threading
import tkinter as tk
import websockets
import edge_tts
import os
import tempfile
import pygame

SERVER = "wss://shout-server-production.up.railway.app"

# Edge TTS 音色，可自行替换
VOICE = "zh-CN-XiaoxiaoNeural"
# 其他可选：
# zh-CN-YunxiNeural    男声，阳光
# zh-CN-YunyangNeural  男声，新闻播报
# zh-CN-XiaoyiNeural   女声，活泼
# zh-CN-liaoning-XiaobeiNeural  东北话女声

pygame.mixer.init()

class ScreenApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("班级大屏")
        self.root.configure(bg="black")
        self.root.withdraw()

        self.label = tk.Label(
            self.root, text="", font=("微软雅黑", 72, "bold"),
            fg="yellow", bg="black", wraplength=1700, justify="center"
        )
        self.label.pack(expand=True)
        self.root.bind("<Escape>", lambda e: self.hide())

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
                        async for msg in ws:
                            self.root.after(0, lambda m=msg: self.show(m))
                except Exception:
                    await asyncio.sleep(3)

        loop.run_until_complete(_listen())

    def show(self, text):
        self.label.config(text=text)
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)
        self.root.lift()
        self.root.focus_force()
        threading.Thread(target=self.speak, args=(text,), daemon=True).start()
        self.root.after(8000, self.hide)

    def speak(self, text):
        try:
            tmp = os.path.join(tempfile.gettempdir(), "shout_voice.mp3")

            async def _tts():
                communicate = edge_tts.Communicate(text, VOICE)
                await communicate.save(tmp)

            asyncio.run(_tts())

            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print("语音播放失败:", e)

    def hide(self):
        self.root.attributes("-fullscreen", False)
        self.root.withdraw()

if __name__ == "__main__":
    ScreenApp()
