import asyncio
import json
import socket
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import websockets
import os
import sys
import requests
import urllib.request
import subprocess
import tempfile
import time
import ssl
import urllib3

# 尝试导入 openpyxl (用于读取 Excel)
try:
    import openpyxl
except ImportError:
    openpyxl = None

# 禁用证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# ================= 配置区 =================
SERVER = "wss://xvxdrz3k3j.sealosbja.site/__websocket__"
GITHUB_REPO = "LWY2010/shout-server"
CURRENT_VERSION = "1.2.1" 
# =========================================

GRADES = ["高一", "高二", "高三"]
CLASS_NUMS = list(range(1, 17))

SINGLE_INSTANCE_PORT = 18889
DATA_DIR = r"C:\ClassroomShout"

def check_update(exe_name="teacher.exe"):
    """后台检查并下载更新"""
    log_path = os.path.join(DATA_DIR, "update_log.txt")
    bat_log = os.path.join(DATA_DIR, "bat_log.txt")
    
    def write_log(msg):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    try:
        time.sleep(5)
        write_log("="*30)
        write_log(f"开始检查更新，当前版本: {CURRENT_VERSION}")
        
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        resp = requests.get(api_url, timeout=10, verify=False)
        write_log(f"API 请求状态码: {resp.status_code}")
        
        if resp.status_code != 200:
            write_log("获取 API 失败，退出更新")
            return

        data = resp.json()
        latest_version = data.get("tag_name", "").lstrip("v")
        write_log(f"GitHub 最新版本: {latest_version}")
        
        if not latest_version or latest_version == CURRENT_VERSION:
            write_log("版本一致，无需更新")
            return

        download_url = None
        for asset in data.get("assets", []):
            if asset["name"] == exe_name:
                download_url = asset["browser_download_url"]
                break
        
        if not download_url:
            write_log(f"未在 Release 中找到 {exe_name}，退出")
            return

        fast_url = download_url.replace("github.com", "ghfast.top/https://github.com")
        write_log(f"开始下载新版: {fast_url}")
        
        temp_exe = os.path.join(tempfile.gettempdir(), f"new_{exe_name}")
        urllib.request.urlretrieve(fast_url, temp_exe)
        write_log("下载完成，准备替换文件")

        current_exe_path = sys.executable
        bat_path = os.path.join(tempfile.gettempdir(), "update_teacher.bat")
        
        bat_content = f"""
@echo off
echo [%date% %time%] BAT脚本启动 >> "{bat_log}"
ping 127.0.0.1 -n 3 > nul
echo [%date% %time%] 尝试结束进程 >> "{bat_log}"
taskkill /f /t /im {exe_name} >> "{bat_log}" 2>&1
ping 127.0.0.1 -n 5 > nul
echo [%date% %time%] 尝试删除旧文件 >> "{bat_log}"
del /f /q /a "{current_exe_path}" >> "{bat_log}" 2>&1
echo [%date% %time%] 尝试移动新文件 >> "{bat_log}"
move /y "{temp_exe}" "{current_exe_path}" >> "{bat_log}" 2>&1
if exist "{current_exe_path}" (
    echo [%date% %time%] 移动成功，清理环境并启动 >> "{bat_log}"
    set PYINSTALLER_RESET_ENVIRONMENT=1
    explorer.exe "{current_exe_path}"
) else (
    echo [%date% %time%] 移动失败，文件不存在 >> "{bat_log}"
)
del "%~f0"
"""
        with open(bat_path, "w", encoding="gbk") as f:
            f.write(bat_content)

        write_log("执行替换脚本，程序即将瞬间退出")
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

def get_roster_path():
    ensure_data_dir()
    return os.path.join(DATA_DIR, "roster.txt")

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
            
        threading.Thread(target=check_update, args=("teacher.exe",), daemon=True).start()

        self.root = tk.Tk()
        self.root.title(f"办公室喊话 v{CURRENT_VERSION}")
        self.root.geometry("820x780")

        self.ws = None
        self.loop = None
        self.username = None
        self.room_vars = {}
        self.grade_vars = {}
        self.status_labels = {}
        self.online_ids = set()
        
        self.students = []
        self.load_local_roster()

        self.saved_user = load_saved_user()
        self.auto_login_pending = bool(self.saved_user)
        self.show_sender_var = tk.BooleanVar(value=False)

        threading.Thread(target=self.connect, daemon=True).start()
        threading.Thread(target=self.listen_single_signal, daemon=True).start()
        self.build_login()
        self.root.mainloop()

    def load_local_roster(self):
        path = get_roster_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.students = [line.strip() for line in f if line.strip()]
            except Exception:
                pass

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
        self.status_labels.clear()

        tk.Label(self.root, text="办公室喊话", font=("微软雅黑", 20, "bold")).pack(pady=25)

        if self.saved_user:
            tk.Label(self.root, text=f"上次登录：{self.saved_user}（正在自动登录...）", font=("微软雅黑", 10), fg="gray").pack()
        else:
            tk.Label(self.root, text="请输入您的名字：", font=("微软雅黑", 12)).pack()

        self.e_user = tk.Entry(self.root, font=("微软雅黑", 13), width=20)
        self.e_user.pack(pady=8)
        if self.saved_user: self.e_user.insert(0, self.saved_user)

        tk.Button(self.root, text="进入", font=("微软雅黑", 13), width=12, bg="#4CAF50", fg="white", command=self.do_login).pack(pady=15)

        self.status = tk.Label(self.root, text="正在连接服务器...", fg="orange", font=("微软雅黑", 10))
        self.status.pack(pady=10)

    def build_main(self):
        self.clear()
        self.room_vars.clear()
        self.grade_vars.clear()
        self.status_labels.clear()

        top = tk.Frame(self.root)
        top.pack(fill="x", padx=15, pady=6)
        tk.Label(top, text=f"欢迎，{self.username}", font=("微软雅黑", 13, "bold")).pack(side="left")
        tk.Button(top, text="退出登录", font=("微软雅黑", 10), bg="#FF9800", fg="white", command=self.do_logout).pack(side="right")

        opt_row = tk.Frame(self.root)
        opt_row.pack(fill="x", padx=15, pady=2)
        tk.Checkbutton(opt_row, text="在大屏上显示我的名字", variable=self.show_sender_var, font=("微软雅黑", 11)).pack(side="left")

        legend = tk.Frame(self.root)
        legend.pack(fill="x", padx=15)
        tk.Label(legend, text="● 在线", fg="green", font=("微软雅黑", 10)).pack(side="left", padx=6)
        tk.Label(legend, text="● 离线", fg="gray", font=("微软雅黑", 10)).pack(side="left", padx=6)

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
                lab = tk.Label(cell, text="●", fg="gray", font=("微软雅黑", 10))
                lab.pack(side="left")
                self.status_labels[rid] = lab

        msg_head = tk.Frame(self.root)
        msg_head.pack(fill="x", padx=15, pady=(8, 0))
        tk.Label(msg_head, text="喊话内容：", font=("微软雅黑", 12)).pack(side="left")
        tk.Button(msg_head, text="📋 导入/选择学生", font=("微软雅黑", 10), bg="#2196F3", fg="white", command=self.open_roster_window).pack(side="right")

        self.msg = tk.Text(self.root, height=5, font=("微软雅黑", 12))
        self.msg.pack(fill="x", padx=15)

        btn_row = tk.Frame(self.root)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="发送喊话", font=("微软雅黑", 13), bg="#4CAF50", fg="white", width=14, command=self.send).pack(side="left", padx=6)
        tk.Button(btn_row, text="全不选", font=("微软雅黑", 11), command=self.clear_all).pack(side="left", padx=6)
        tk.Button(btn_row, text="只选在线", font=("微软雅黑", 11), command=self.select_online).pack(side="left", padx=6)

        self.status = tk.Label(self.root, text="就绪", fg="green", font=("微软雅黑", 10))
        self.status.pack(pady=4)

    def open_roster_window(self):
        win = tk.Toplevel(self.root)
        win.title("学生花名册")
        win.geometry("400x500")
        win.attributes("-topmost", True)

        toolbar = tk.Frame(win)
        toolbar.pack(fill="x", padx=10, pady=10)

        tk.Button(toolbar, text="导入名单 (.xlsx/.txt/.csv)", command=lambda: self.import_roster(win)).pack(side="left")

        search_frame = tk.Frame(win)
        search_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(search_frame, text="搜索：").pack(side="left")
        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=search_var, font=("微软雅黑", 11))
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.focus_set()

        list_frame = tk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        listbox = tk.Listbox(list_frame, font=("微软雅黑", 12), yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)

        def refresh_list(*args):
            keyword = search_var.get().strip()
            listbox.delete(0, tk.END)
            for name in self.students:
                if keyword in name:
                    listbox.insert(tk.END, name)

        def on_select(event):
            selection = listbox.curselection()
            if selection:
                name = listbox.get(selection[0])
                self.msg.insert(tk.END, f"{name} ")
                self.msg.see(tk.END)  
                win.destroy() 

        search_var.trace_add("write", refresh_list)
        listbox.bind("<Double-Button-1>", on_select) 
        listbox.bind("<Return>", on_select) 

        refresh_list()

    def import_roster(self, parent_win):
        file_path = filedialog.askopenfilename(
            parent=parent_win,
            title="选择学生名单文件",
            filetypes=[("Excel 文件", "*.xlsx"), ("文本文件", "*.txt"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not file_path:
            return

        new_names = []
        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext == ".xlsx":
                if openpyxl is None:
                    messagebox.showerror("错误", "缺少 openpyxl 库，无法读取 Excel。请使用 .txt 或 .csv", parent=parent_win)
                    return
                
                # 读取 Excel
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                sheet = wb.active # 默认读取第一个表
                for row in sheet.iter_rows(values_only=True):
                    if row and row[0]: # 读取第一列，且不为空
                        name = str(row[0]).strip()
                        if name and name != "姓名" and name != "名字":
                            new_names.append(name)
                wb.close()

            else:
                # 读取文本或 CSV
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    content = content.replace(",", "\n").replace("，", "\n")
                    new_names = [line.strip() for line in content.splitlines() if line.strip()]

            if not new_names:
                messagebox.showwarning("提示", "没有读取到有效的名字", parent=parent_win)
                return

            self.students = new_names
            
            with open(get_roster_path(), "w", encoding="utf-8") as f:
                for name in self.students:
                    f.write(name + "\n")

            messagebox.showinfo("成功", f"成功导入 {len(self.students)} 名学生！\n名单已自动保存。", parent=parent_win)
            parent_win.destroy()
            self.open_roster_window()

        except Exception as e:
            messagebox.showerror("错误", f"导入失败：{e}\n（如果文件正在被 Excel 打开，请先关闭 Excel）", parent=parent_win)

    def toggle_grade(self, grade):
        val = self.grade_vars[grade].get()
        for rid, var in self.room_vars.items():
            if rid.startswith(grade): var.set(val)

    def clear_all(self):
        for v in self.room_vars.values(): v.set(False)
        for v in self.grade_vars.values(): v.set(False)

    def select_online(self):
        for rid, var in self.room_vars.items():
            var.set(rid in self.online_ids)

    def connect(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._conn())

    async def _conn(self):
        while True:
            try:
                async with websockets.connect(SERVER) as ws:
                    self.ws = ws
                    self.root.after(0, lambda: self.status.config(text="已连接", fg="green"))
                    if self.auto_login_pending and self.saved_user:
                        self.auto_login_pending = False
                        self.root.after(500, self._auto_login)
                    async for raw in ws:
                        msg = json.loads(raw)
                        self.root.after(0, lambda m=msg: self.handle(m))
            except Exception:
                self.ws = None
                self.root.after(0, lambda: self.status.config(text="连接断开，重试中...", fg="red"))
                await asyncio.sleep(3)

    def _auto_login(self):
        if not self.ws:
            self.auto_login_pending = True
            return
        self.send_json({"action": "teacher_login", "username": self.saved_user})

    def send_json(self, obj):
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(obj, ensure_ascii=False)), self.loop)

    def handle(self, msg):
        t = msg.get("type")
        if t == "login_ok":
            self.username = msg["username"]
            self.build_main()
            self.apply_status(self.online_ids)
        elif t == "room_status":
            self.online_ids = set(msg.get("online", []))
            self.apply_status(self.online_ids)
        elif t == "sent":
            self.status.config(text=f"已发送给 {msg.get('count',0)} 个在线班级", fg="blue")
        elif t == "error":
            messagebox.showerror("错误", msg.get("msg", "未知错误"))

    def apply_status(self, online_ids):
        for rid, lab in self.status_labels.items():
            if not lab.winfo_exists(): continue
            lab.config(fg="green" if rid in online_ids else "gray")

    def do_login(self):
        name = self.e_user.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入名字")
            return
        save_user(name)
        self.saved_user = name
        self.send_json({"action": "teacher_login", "username": name})

    def do_logout(self):
        if not messagebox.askyesno("确认", "退出登录后需要重新输入名字，确定吗？"): return
        clear_saved_user()
        self.saved_user = ""
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
        self.send_json({
            "action": "shout",
            "room_ids": targets,
            "text": text,
            "show_sender": self.show_sender_var.get()
        })
        self.msg.delete("1.0", "end")

if __name__ == "__main__":
    TeacherApp()
