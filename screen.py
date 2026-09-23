import asyncio
import json
import socket
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import websockets
import edge_tts
import os
import sys
import tempfile
import pygame
import uuid
import winreg
import pystray
from PIL import Image, ImageDraw

SERVER = "wss://shout-server-production.up.railway.app"
VOICE = "zh-CN-XiaoxiaoNeural"

GRADES = ["高一", "高二", "高三"]
CLASS_NUMS = list(range(1, 17))

pygame.mixer.init()

current_play_id = 0
play_id_lock = threading.Lock()

APP_NAME = "ClassroomScreen"

MIN_DISPLAY_SECONDS = 20
STARTUP_WINDOW_SECONDS = 5     # 启动窗口显示时长（秒）

SINGLE_INSTANCE_PORT = 18888

# 数据固定存放目录
DATA_DIR = r"C:\ClassroomShout"


# ---------- 单实例 ----------
def try_acquire_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        return s, True
    except OSError:
        try:
            s.close()
        except Exception:
            pass
        return None, False


def notify_existing_instance():
    try:
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.settimeout(2)
        c.connect(("127.0.0.1", SINGLE_INSTANCE_PORT))
        c.send(b"SHOW")
        c.close()
    except Exception as e:
        print("通知已有实例失败:", e)


# ---------- 路径 / 配置 ----------
def ensure_data_dir():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception as e:
        print("创建数据目录失败:", e)


def get_config_path():
    ensure_data_dir()
    return os.path.join(DATA_DIR, "room.json")


def get_auth_path():
    ensure_data_dir()
    return os.path.join(DATA_DIR, "auth.dat")


def load_password():
    path = get_auth_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                pwd = f.read().strip()
                if pwd:
                    return pwd
        except Exception:
            pass
    return "01180204"


def load_room():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
                rid = d.get("room_id")
                if rid:
                    return rid
        except Exception:
            pass
    return None


def save_room(room_id):
    try:
        with open(get_config_path(), "w", encoding="utf-8") as f:
            json.dump({"room_id": room_id}, f, ensure_ascii=False)
    except Exception as e:
        print("保存班级配置失败:", e)


def clear_room():
    try:
        path = get_config_path()
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print("清除配置失败:", e)


def is_autostart_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_QUERY_VALUE)
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
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        if enable:
            if getattr(sys, "frozen", False):
                exe_path = sys.executable
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print("设置开机自启失败:", e)


# ---------- 托盘 ----------
def make_tray_image():
    img = Image.new("RGB", (64, 64), color="black")
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, 52, 52], fill="#FFD700")
    d.rectangle([20, 20, 44, 44], fill="black")
    return img


def run_tray(app):
    def on_quit(icon, item):
        try:
            icon.stop()
        except Exception:
            pass
        try:
            app.root.quit()
            app.root.destroy()
        except Exception:
            pass

    menu = pystray.Menu(
        pystray.MenuItem("退出程序", on_quit),
    )
    icon = pystray.Icon("ClassroomScreen", make_tray_image(), "教室大屏", menu)
    app.tray_icon = icon
    icon.run()


class ScreenApp:
    def __init__(self):
        self.single_sock, is_first = try_acquire_single_instance()
        if not is_first:
            notify_existing_instance()
            sys.exit(0)

        self.root = tk.Tk()
        self.root.title("班级大屏")
        self.root.configure(bg="black")

        self.room_id = None
        self.sender_label = None
        self.label = None
        self.ws = None
        self.state_label = None
        self.tray_icon = None
        self.startup_done = True
        self.ack_btn = None

        self.root.protocol("WM_DELETE_WINDOW", self.on_close_attempt)

        if "--reset" in sys.argv:
            clear_room()
            print("已清除班级配置")

        self.room_id = load_room()

        if self.room_id is None:
            self.show_select_window()
        else:
            self.show_startup_window()

        self.root.bind("<Escape>", lambda e: self.hide())

        threading.Thread(target=run_tray, args=(self,), daemon=True).start()
        threading.Thread(target=self.listen, daemon=True).start()
        threading.Thread(target=self.listen_single_signal, daemon=True).start()

        self.root.mainloop()

    def listen_single_signal(self):
        while True:
            try:
                conn, _ = self.single_sock.accept()
                try:
                    data = conn.recv(16)
                except Exception:
                    data = b""
                try:
                    conn.close()
                except Exception:
                    pass
                if data == b"SHOW":
                    self.root.after(0, self.bring_to_front)
            except Exception:
                break

    def bring_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(800, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception as e:
            print("激活窗口失败:", e)

    def on_close_attempt(self):
        if not self.startup_done:
            self.close_startup()
        else:
            self.hide()

    def show_select_window(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("480x320")
        self.root.resizable(False, False)
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = (sw - 480) // 2, (sh - 320) // 2
        self.root.geometry(f"480x320+{x}+{y}")
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(500, lambda: self.root.attributes("-topmost", False))

        tk.Label(self.root, text="请选择本教室的班级",
                 font=("微软雅黑", 16, "bold"), fg="white", bg="black").pack(pady=20)

        row = tk.Frame(self.root, bg="black")
        row.pack(pady=10)

        self.grade_var = tk.StringVar(value="高一")
        grade_cb = ttk.Combobox(row, textvariable=self.grade_var,
                                values=GRADES, state="readonly",
                                font=("微软雅黑", 12), width=6)
        grade_cb.pack(side="left", padx=6)

        self.num_var = tk.StringVar(value="1班")
        num_cb = ttk.Combobox(row, textvariable=self.num_var,
                              values=[f"{n}班" for n in CLASS_NUMS],
                              state="readonly",
                              font=("微软雅黑", 12), width=6)
        num_cb.pack(side="left", padx=6)

        tk.Button(self.root, text="确定",
                  font=("微软雅黑", 13), width=10,
                  bg="#4CAF50", fg="white",
                  command=self.confirm_room).pack(pady=20)

    def confirm_room(self):
        rid = f"{self.grade_var.get()}{self.num_var.get()}"
        save_room(rid)
        self.room_id = rid
        for w in self.root.winfo_children():
            w.destroy()
        self.show_startup_window()

    def show_startup_window(self):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("480x360")
        self.root.resizable(False, False)
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x, y = (sw - 480) // 2, (sh - 360) // 2
        self.root.geometry(f"480x360+{x}+{y}")

        # 前台显示
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.after(1000, lambda: self.root.attributes("-topmost", False))

        tk.Label(self.root, text="✅ 教室大屏已启动",
                 font=("微软雅黑", 16, "bold"), fg="white", bg="black").pack(pady=(15, 4))
        tk.Label(self.root, text=f"班级：{self.room_id}",
                 font=("微软雅黑", 13, "bold"), fg="#FFD700", bg="black").pack(pady=4)

        self.state_label = tk.Label(self.root, text="正在连接服务器...",
                                    font=("微软雅黑", 11), fg="orange", bg="black")
        self.state_label.pack(pady=8)

        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        tk.Checkbutton(self.root, text="开机自动启动",
                       variable=self.autostart_var,
                       font=("微软雅黑", 11),
                       fg="white", bg="black", selectcolor="#333",
                       activebackground="black", activeforeground="white").pack(pady=6)

        btn_row = tk.Frame(self.root, bg="black")
        btn_row.pack(pady=6)
        tk.Button(btn_row, text="关闭提示，进入后台",
                  font=("微软雅黑", 11),
                  bg="#4CAF50", fg="white",
                  command=self.close_startup).pack(side="left", padx=5)
        tk.Button(btn_row, text="重新选择班级",
                  font=("微软雅黑", 11),
                  bg="#FF9800", fg="white",
                  command=self.reset_room).pack(side="left", padx=5)

        self.startup_done = False
        self.root.after(STARTUP_WINDOW_SECONDS * 1000, self._auto_close_startup)

    def _auto_close_startup(self):
        if not self.startup_done:
            self.close_startup()

    def close_startup(self):
        self.startup_done = True
        try:
            set_autostart(self.autostart_var.get())
        except Exception:
            pass
        for w in self.root.winfo_children():
            w.destroy()

        self.sender_label = tk.Label(
            self.root, text="",
            font=("微软雅黑", 28, "bold"),
            fg="#90EE90", bg="black"
        )
        self.sender_label.pack(side="top", pady=(40, 0))

        self.label = tk.Label(
            self.root, text="",
            font=("微软雅黑", 72, "bold"),
            fg="yellow", bg="black",
            wraplength=1700, justify="center"
        )
        self.label.pack(expand=True)

        self.root.withdraw()

    def reset_room(self):
        pwd = simpledialog.askstring(
            "请输入管理密码",
            "清除配置需要密码，请联系管理员：",
            show="*",
            parent=self.root
        )
        if pwd is None:
            return
        if pwd != load_password():
            messagebox.showerror("错误", "密码错误")
            return
        if not messagebox.askyesno("确认", "确定要清除当前班级配置，重新选择吗？"):
            return
        clear_room()
        self.room_id = None
        self.show_select_window()

    def set_state_online(self):
        if self.state_label and self.state_label.winfo_exists():
            self.state_label.config(text="✅ 已连接服务器", fg="green")

    def listen(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._listen())

    async def _listen(self):
        while True:
            try:
                if not self.room_id:
                    await asyncio.sleep(1)
                    continue
                async with websockets.connect(SERVER) as ws:
                    self.ws = ws
                    await ws.send(json.dumps({
                        "action": "room_hello",
                        "room_id": self.room_id
                    }, ensure_ascii=False))
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("type") == "room_ok":
                            self.root.after(0, self.set_state_online)
                        elif msg.get("type") == "shout":
                            text = msg.get("text", "")
                            sender = msg.get("sender", "")
                            self.root.after(0, lambda t=text, s=sender: self.show(t, s))
            except Exception:
                await asyncio.sleep(3)

    def calc_font_and_wrap(self, text):
        n = len(text)
        if n <= 3:
            size = 160
        elif n <= 6:
            size = 130
        elif n <= 10:
            size = 110
        elif n <= 20:
            size = 85
        elif n <= 35:
            size = 65
        elif n <= 60:
            size = 50
        elif n <= 100:
            size = 38
        else:
            size = 30
        wrap = self.root.winfo_screenwidth() - 200
        return size, wrap

    def show(self, text, sender=""):
        if not self.label:
            return
        size, wrap = self.calc_font_and_wrap(text)

        if self.sender_label and self.sender_label.winfo_exists():
            if sender:
                self.sender_label.config(text=f"来自 {sender}")
            else:
                self.sender_label.config(text="")

        self.label.config(text=text,
                          font=("微软雅黑", size, "bold"),
                          wraplength=wrap,
                          justify="center")
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)
        self.root.lift()
        self.root.focus_force()

        if self.ack_btn:
            try:
                self.ack_btn.destroy()
            except Exception:
                pass
            self.ack_btn = None

        self.ack_btn = tk.Button(
            self.root, text="我知道了 ✓",
            font=("微软雅黑", 18, "bold"),
            bg="#4CAF50", fg="white",
            activebackground="#45a049", activeforeground="white",
            padx=30, pady=15,
            command=self.acknowledge
        )
        self.ack_btn.place(relx=0.97, rely=0.95, anchor="se")
        self.ack_btn.lift()

        threading.Thread(target=self.play_and_wait, args=(text,), daemon=True).start()

    def acknowledge(self):
        global current_play_id
        with play_id_lock:
            current_play_id += 1
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.root.after(0, self.hide)

    def play_and_wait(self, text):
        global current_play_id
        with play_id_lock:
            current_play_id += 1
            my_id = current_play_id

        start_time = time.time()

        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

        tmp = None
        try:
            tmp = os.path.join(tempfile.gettempdir(), f"shout_{uuid.uuid4().hex}.mp3")

            async def _tts():
                communicate = edge_tts.Communicate(text, VOICE)
                await communicate.save(tmp)

            asyncio.run(_tts())

            with play_id_lock:
                if my_id != current_play_id:
                    if tmp and os.path.exists(tmp):
                        try: os.remove(tmp)
                        except Exception: pass
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
                if my_id != current_play_id:
                    return

            elapsed = time.time() - start_time
            remain = MIN_DISPLAY_SECONDS - elapsed
            while remain > 0:
                time.sleep(0.2)
                remain -= 0.2
                with play_id_lock:
                    if my_id != current_play_id:
                        return

            with play_id_lock:
                if my_id == current_play_id:
                    self.root.after(0, self.hide)

        except Exception as e:
            print("语音播放失败:", e)
            elapsed = time.time() - start_time
            remain = MIN_DISPLAY_SECONDS - elapsed
            while remain > 0:
                time.sleep(0.2)
                remain -= 0.2
                with play_id_lock:
                    if my_id != current_play_id:
                        return
            with play_id_lock:
                if my_id == current_play_id:
                    self.root.after(0, self.hide)
        finally:
            if tmp and os.path.exists(tmp):
                try: os.remove(tmp)
                except Exception: pass

    def hide(self):
        if self.ack_btn:
            try:
                self.ack_btn.destroy()
            except Exception:
                pass
            self.ack_btn = None
        self.root.attributes("-fullscreen", False)
        self.root.withdraw()


if __name__ == "__main__":
    ScreenApp()
