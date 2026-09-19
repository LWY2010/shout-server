import asyncio
import threading
import tkinter as tk
import websockets
import edge_tts
import os
import sys
import tempfile
import pygame
import uuid
import winreg

SERVER = "wss://shout-server-production.up.railway.app"

VOICE = "zh-CN-XiaoxiaoNeural"

pygame.mixer.init()

current_play_id = 0
play_id_lock = threading.Lock()

APP_NAME = "ClassroomScreen"   # 启动项里的名字，不要改


def is_autostart_enabled():
    """检查当前是否已在启动项里"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_QUERY_VALUE
        )
        try:
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def set_autostart(enable=True):
    """开启或关闭开机自启"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        if enable:
            if getattr(sys, "frozen", False):
                exe_path = sys.executable
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
            print("已设置开机自启")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                print("已取消开机自启")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print("设置开机自启失败:", e)


class ScreenApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("班级大屏")
        self.root.configure(bg="black")

        self.show_startup_window()

        self.label = tk.Label(
            self.root, text="", font=("微软雅黑", 72, "bold"),
            fg="yellow", bg="black", wraplength=1700, justify="center"
        )

        self.root.bind("<Escape>", lambda e: self.hide())

        threading.Thread(target=self.listen, daemon=True).start()
        self.root.mainloop()

    def show_startup_window(self):
        self.root.geometry("440x260")
        self.root.resizable(False, False)

        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - 440) // 2
        y = (screen_h - 260) // 2
        self.root.geometry(f"440x260+{x}+{y}")

        tk.Label(
            self.root,
            text="✅ 教室大屏已启动",
            font=("微软雅黑", 16, "bold"),
            fg="white", bg="black"
        ).pack(pady=(18, 6))

        tk.Label(
            self.root,
            text="正在后台等待喊话...",
            font=("微软雅黑", 12),
            fg="gray", bg="black"
        ).pack()

        # 开机自启勾选框
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        tk.Checkbutton(
            self.root,
            text="开机自动启动",
            variable=self.autostart_var,
            font=("微软雅黑", 12),
            fg="white", bg="black",
            selectcolor="#333",
            activebackground="black",
            activeforeground="white"
        ).pack(pady=15)

        tk.Button(
            self.root, text="关闭提示",
            font=("微软雅黑", 12),
            bg="#4CAF50", fg="white",
            width=12,
            command=self.close_startup
        ).pack(pady=5)

    def close_startup(self):
        # 按勾选状态设置自启
        set_autostart(self.autostart_var.get())

        # 清空窗口控件
        for w in self.root.winfo_children():
            w.destroy()

        # 重建喊话用的 label
        self.label = tk.Label(
            self.root, text="", font=("微软雅黑", 72, "bold"),
            fg="yellow", bg="black", wraplength=1700, justify="center"
        )
        self.label.pack(expand=True)
        self.root.withdraw()

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
