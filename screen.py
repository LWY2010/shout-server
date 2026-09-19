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

current_play_id = 0
play_id_lock = threading.Lock()


class ScreenApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("班级大屏")
        self.root.configure(bg="black")

        # 启动提示窗口（小窗，居中）
        self.show_startup_window()

        # 真正的显示标签（用于喊话）
        self.label = tk.Label(
            self.root, text="", font=("微软雅黑", 72, "bold"),
            fg="yellow", bg="black", wraplength=1700, justify="center"
        )

        self.root.bind("<Escape>", lambda e: self.hide())

        threading.Thread(target=self.listen, daemon=True).start()
        self.root.mainloop()

    def show_startup_window(self):
        """开机启动时显示的小提示窗口"""
        self.root.geometry("400x200")
        self.root.resizable(False, False)

        # 居中显示
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - 400) // 2
        y = (screen_h - 200) // 2
        self.root.geometry(f"400x200+{x}+{y}")

        self.startup_label = tk.Label(
            self.root,
            text="✅ 教室大屏已启动\n\n正在后台等待喊话...\n\n点击下方按钮关闭此提示",
            font=("微软雅黑", 14),
            fg="white", bg="black", justify="center"
        )
        self.startup_label.pack(expand=True, pady=10)

        tk.Button(
            self.root, text="关闭提示",
            font=("微软雅黑", 12),
            bg="#4CAF50", fg="white",
            command=self.close_startup
        ).pack(pady=10)

    def close_startup(self):
        """关闭启动提示，进入后台待命"""
        self.startup_label.destroy()
        for w in self.root.winfo_children():
            w.destroy()
        # 重新挂上喊话用的 label
        self.label = tk.Label(
            self.root, text="", font=("微软雅黑", 72, "bold"),
            fg="yellow", bg="black", wraplength=1700, justify="center"
        )
        self.label.pack(expand=True)
        self.root.withdraw()   # 隐藏到后台

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

    def speak(self, text):
        global current_play_id

        with play_id_lock:
            current_play_id += 1
            my_id = current_play_id

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

            async def _tts():
                communicate = edge_tts.Communicate(text, VOICE)
                await communicate.save(tmp)

            asyncio.run(_tts())

            with play_id_lock:
                if my_id != current_play_id:
                    if tmp and os.path.exists(tmp):
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass
                    return

            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                with play_id_lock:
                    if my_id != current_play_id:
                        pygame.mixer.music.stop()
                        break
                pygame.time.Clock().tick(10)

            with play_id_lock:
                if my_id == current_play_id:
                    self.root.after(0, self.hide)

        except Exception as e:
            print("语音播放失败:", e)
            self.root.after(0, self.hide)
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    def hide(self):
        self.root.attributes("-fullscreen", False)
        self.root.withdraw()


if __name__ == "__main__":
    ScreenApp()
