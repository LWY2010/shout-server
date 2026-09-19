import asyncio
import threading
import tkinter as tk
import websockets
import edge_tts
import os
import tempfile
import pygame
import uuid

SERVER = "wss://shout-server-production.up.railway.app"

# Edge TTS 音色，可自行替换
VOICE = "zh-CN-XiaoxiaoNeural"
# 其他可选：
# zh-CN-YunxiNeural    男声，阳光
# zh-CN-YunyangNeural  男声，新闻播报
# zh-CN-XiaoyiNeural   女声，活泼
# zh-CN-liaoning-XiaobeiNeural  东北话女声

pygame.mixer.init()

# 用于控制打断：每次新消息递增，播放线程检查是否过期
current_play_id = 0
play_id_lock = threading.Lock()


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
        """合成并播放语音，新消息会立刻打断旧消息"""
        global current_play_id

        # 生成本次播放的唯一 ID
        with play_id_lock:
            current_play_id += 1
            my_id = current_play_id

        # 先立即打断当前正在播放的语音
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

        tmp = None
        try:
            tmp = os.path.join(
                tempfile.gettempdir(),
                f"shout_{uuid.uuid4().hex}.mp3"
            )

            # 合成语音
            async def _tts():
                communicate = edge_tts.Communicate(text, VOICE)
                await communicate.save(tmp)

            asyncio.run(_tts())

            # 合成期间如果来了新消息，直接放弃本次播放
            with play_id_lock:
                if my_id != current_play_id:
                    if tmp and os.path.exists(tmp):
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
                    return

            # 再次确保没有更新的消息
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()

            # 边播边检查是否被新消息打断
            while pygame.mixer.music.get_busy():
                with play_id_lock:
                    if my_id != current_play_id:
                        pygame.mixer.music.stop()
                        break
                pygame.time.Clock().tick(10)

        except Exception as e:
            print("语音播放失败:", e)
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass


if __name__ == "__main__":
    ScreenApp()
