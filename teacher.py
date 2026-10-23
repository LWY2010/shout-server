import socket
import threading
import tkinter as tk
from tkinter import messagebox
import os
import sys
import requests
import urllib.request
import subprocess
import tempfile
import time
import ssl
import urllib3
import json
from apinator import Apinator

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# ================= 配置区 =================
APP_ID = "4f6d7654-5851-4b86-a0ea-4238a261d49b"
APP_KEY = "app_0f98d696964886b64f1b12114923b79201fcdf31"
APP_SECRET = "433c839e1257efd0668ba4dcbdc537958c1bd467b291f46c7df096cff5573586"
CLUSTER = "us" 

GITHUB_REPO = "LWY2010/shout-server"
CURRENT_VERSION = "1.0.0" 
# =========================================

GRADES = ["高一", "高二", "高三"]
CLASS_NUMS = list(range(1, 17))

SINGLE_INSTANCE_PORT = 18889
DATA_DIR = r"C:\ClassroomShout"

def check_update(exe_name="teacher.exe"):
    log_path = os.path.join(DATA_DIR, "update_log.txt")
    
    def write_log(msg):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    try:
        time.sleep(5)
        
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        resp = requests.get(api_url, timeout=10, verify=False)
        
        if resp.status_code != 200:
            return

        data = resp.json()
        latest_version = data.get("tag_name", "").lstrip("v")
        
        if not latest_version or latest_version == CURRENT_VERSION:
            return

        download_url = None
        for asset in data.get("assets", []):
            if asset["name"] == exe_name:
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            return

        ans = messagebox.askyesno("发现新版本", f"检测到新版本 {latest_version}，是否立即下载更新？\n（下载期间您可以继续使用）")
        if not ans:
            return

        fast_url = download_url.replace("github.com", "ghfast.top/https://github.com")
        
        temp_exe = os.path.join(tempfile.gettempdir(), f"new_{exe_name}")
        urllib.request.urlretrieve(fast_url, temp_exe)
        write_log("下载完成")

        ans2 = messagebox.askyesno("下载完成", "新版本已下载完毕。\n点击“是”将立即重启并应用更新。\n（请注意保存当前操作）")
        if not ans2:
            return

        current_exe_path = sys.executable
        bat_path = os.path.join(tempfile.gettempdir(), "update_teacher.bat")
        
        bat_content = f"""
@echo off
ping 127.0.0.1 -n 3 > nul
taskkill /f /im "{exe_name}" > nul 2>&1
ping 127.0.0.1 -n 3 > nul
del /f /q "{current_exe_path}" > nul 2>&1
move /y "{temp_exe}" "{current_exe_path}" > nul 2>&1
set PYINSTALLER_RESET_ENVIRONMENT=1
start "" "{current_exe_path}"
del "%~f0"
"""
        with open(bat_path, "w", encoding="gbk") as f:
            f.write(bat_content)

        subprocess.Popen(bat_path, shell=True)
        os._exit(0)

    except Exception as e:
        write_log(f"发生异常: {str(e)}")

def try_acquire_single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
        return s, True
    except OSError:
        try: s.close()
        except Exception: pass
        return None, False

def notify_existing_instance():
    try:
        c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.settimeout(2)
        c.connect(("127.0.0.1", SINGLE_INSTANCE_PORT))
        c.send(b"SHOW")
        c.close()
    except Exception: pass

def ensure_data_dir():
    try: os.makedirs(DATA_DIR, exist_ok=True)
    except Exception: pass

def get_save_path():
    ensure_data_dir()
    return os.path.join(DATA_DIR, "teacher_user.txt")

def load_saved_user():
    path = get_save_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                name = f.read().strip()
                if name: return name
        except Exception: pass
    return ""

def save_user(name):
    try:
        with open(get_save_path(), "w", encoding="utf-8") as f:
            f.write(name)
    except Exception: pass

def clear_saved_user():
    try:
        path = get_save_path()
        if os.path.exists(path): os.remove(path)
    except Exception: pass

class TeacherApp:
    def __init__(self):
        self.single_sock, is_first = try_acquire_single_instance()
        if not is_first:
            notify_existing_instance()
            sys.exit(0)
            
        self.apinator = Apinator(
            app_id=APP_ID,
            key=APP_KEY,
            secret=APP_SECRET,
            cluster=CLUSTER
        )

        threading.Thread(target=check_update, args=("teacher.exe",), daemon=True).start()

        self.root = tk.Tk()
        self.root.title(f"办公室喊话 v{CURRENT_VERSION}")
        self.root.geometry("820x780")

        self.username = None
        self.room_vars = {}
        self.grade_vars = {}
        self.show_sender_var = tk.BooleanVar(value=False)

        threading.Thread(target=self.listen_single_signal, daemon=True).start()
        self.build_login()
        self.root.mainloop()

    def listen_single_signal(self):
        while True:
            try:
                conn, _ = self.single_sock.accept()
                try: data = conn.recv(16)
                except Exception: data = b""
                try: conn.close()
                except Exception: pass
                if data == b"SHOW":
                    self.root.after(0, self.bring_to_front)
            except Exception: break

    def bring_to_front(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(800, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception: pass

    def clear(self):
        for w in self.root.winfo_children(): w.destroy()

    def build_login(self):
        self.clear()
        self.username = None
        self.room_vars.clear()
        self.grade_vars.clear()

        tk.Label(self.root, text="办公室喊话", font=("微软雅黑", 20, "bold")).pack(pady=25)

        if load_saved_user():
            tk.Label(self.root, text=f"上次登录：{load_saved_user()}", font=("微软雅黑", 10), fg="gray").pack()
        else:
            tk.Label(self.root, text="请输入您的名字：", font=("微软雅黑", 12)).pack()

        self.e_user = tk.Entry(self.root, font=("微软雅黑", 13), width=20)
        self.e_user.pack(pady=8)
        if load_saved_user(): self.e_user.insert(0, load_saved_user())

        tk.Button(self.root, text="进入", font=("微软雅黑", 13), width=12, bg="#4CAF50", fg="white", command=self.do_login).pack(pady=15)

        self.status = tk.Label(self.root, text="云端直连模式", fg="green", font=("微软雅黑", 10))
        self.status.pack(pady=10)

    def build_main(self):
        self.clear()
        self.room_vars.clear()
        self.grade_vars.clear()

        top = tk.Frame(self.root)
        top.pack(fill="x", padx=15, pady=6)
        tk.Label(top, text=f"欢迎，{self.username}", font=("微软雅黑", 13, "bold")).pack(side="left")
        tk.Button(top, text="退出登录", font=("微软雅黑", 10), bg="#FF9800", fg="white", command=self.do_logout).pack(side="right")

        opt_row = tk.Frame(self.root)
        opt_row.pack(fill="x", padx=15, pady=2)
        tk.Checkbutton(opt_row, text="在大屏上显示我的名字", variable=self.show_sender_var, font=("微软雅黑", 11)).pack(side="left")

        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=15, pady=4)

        for g in GRADES:
            self.grade_vars[g] = tk.BooleanVar(value=False)
            frame = tk.LabelFrame(container, text="", font=("微软雅黑", 11), bd=1, relief="groove")
            frame.pack(fill="x", pady=4)

            head = tk.Frame(frame)
            head.pack(fill="x", padx=6, pady=(4, 2))
            tk.Label(head, text=g, font=("微软雅黑", 12, "bold"), width=5, anchor="w").pack(side="left")
            tk.Checkbutton(head, text="全选", variable=self.grade_vars[g], font=("微软雅黑", 10), command=lambda gg=g: self.toggle_grade(gg)).pack(side="left")

            grid = tk.Frame(frame)
            grid.pack(fill="x", padx=6, pady=(0, 6))
            for i, n in enumerate(CLASS_NUMS):
                rid = f"{g}{n}班"
                var = tk.BooleanVar(value=False)
                self.room_vars[rid] = var
                cell = tk.Frame(grid)
                cell.grid(row=i // 8, column=i % 8, padx=2, pady=1, sticky="w")
                tk.Checkbutton(cell, text=f"{n}班", variable=var, font=("微软雅黑", 10)).pack(side="left")
                lab = tk.Label(cell, text="●", fg="green", font=("微软雅黑", 10))
                lab.pack(side="left")

        tk.Label(self.root, text="喊话内容：", font=("微软雅黑", 12)).pack(anchor="w", padx=15, pady=(8, 0))
        self.msg = tk.Text(self.root, height=5, font=("微软雅黑", 12))
        self.msg.pack(fill="x", padx=15)

        btn_row = tk.Frame(self.root)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="发送喊话", font=("微软雅黑", 13), bg="#4CAF50", fg="white", width=14, command=self.send).pack(side="left", padx=6)
        tk.Button(btn_row, text="全不选", font=("微软雅黑", 11), command=self.clear_all).pack(side="left", padx=6)

        self.status = tk.Label(self.root, text="就绪", fg="green", font=("微软雅黑", 10))
        self.status.pack(pady=4)

    def toggle_grade(self, grade):
        val = self.grade_vars[grade].get()
        for rid, var in self.room_vars.items():
            if rid.startswith(grade): var.set(val)

    def clear_all(self):
        for v in self.room_vars.values(): v.set(False)
        for v in self.grade_vars.values(): v.set(False)

    def do_login(self):
        name = self.e_user.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入名字")
            return
        save_user(name)
        self.username = name
        self.build_main()

    def do_logout(self):
        if not messagebox.askyesno("确认", "退出登录后需要重新输入名字，确定吗？"): return
        clear_saved_user()
        self.username = None
        self.build_login()

    def send(self):
        text = self.msg.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("提示", "请输入喊话内容")
            return
        targets = [rid for rid, var in self.room_vars.items() if var.get()]
        if not targets:
            messagebox.showwarning("提示", "请先勾选至少一个班级")
            return

        try:
            payload = {
                "text": text,
                "sender": self.username if self.show_sender_var.get() else ""
            }
            for room_id in targets:
                channel_name = f"room-{room_id}"
                self.apinator.trigger(
                    "shout",
                    json.dumps(payload, ensure_ascii=False),
                    channel=channel_name
                )
            self.status.config(text=f"已发送给 {len(targets)} 个班级", fg="blue")
            self.msg.delete("1.0", "end")
        except Exception as e:
            messagebox.showerror("发送失败", f"网络请求失败：{e}")

if __name__ == "__main__":
    TeacherApp()
