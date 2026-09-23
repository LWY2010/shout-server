import asyncio
import json
import socket
import threading
import tkinter as tk
from tkinter import messagebox
import websockets
import os
import sys

SERVER = "wss://shout-server-production.up.railway.app"

GRADES = ["高一", "高二", "高三"]
CLASS_NUMS = list(range(1, 17))

SINGLE_INSTANCE_PORT = 18889


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


def get_save_path():
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "teacher_user.txt")


def load_saved_user():
    path = get_save_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                name = f.read().strip()
                if name:
                    return name
        except Exception:
            pass
    return ""


def save_user(name):
    try:
        with open(get_save_path(), "w", encoding="utf-8") as f:
            f.write(name)
    except Exception as e:
        print("保存登录名字失败:", e)


def clear_saved_user():
    try:
        path = get_save_path()
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print("清除登录名字失败:", e)


class TeacherApp:
    def __init__(self):
        self.single_sock, is_first = try_acquire_single_instance()
        if not is_first:
            notify_existing_instance()
            sys.exit(0)

        self.root = tk.Tk()
        self.root.title("办公室喊话")
        self.root.geometry("820x780")

        self.ws = None
        self.loop = None
        self.username = None
        self.room_vars = {}
        self.grade_vars = {}
        self.status_labels = {}
        self.online_ids = set()

        self.saved_user = load_saved_user()
        self.auto_login_pending = bool(self.saved_user)

        # 是否显示发送者名字（默认勾选）
        self.show_sender_var = tk.BooleanVar(value=True)

        threading.Thread(target=self.connect, daemon=True).start()
        threading.Thread(target=self.listen_single_signal, daemon=True).start()
        self.build_login()
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

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def build_login(self):
        self.clear()
        self.username = None
        self.room_vars.clear()
        self.grade_vars.clear()
        self.status_labels.clear()

        tk.Label(self.root, text="办公室喊话",
                 font=("微软雅黑", 20, "bold")).pack(pady=25)

        if self.saved_user:
            tk.Label(self.root,
                     text=f"上次登录：{self.saved_user}（正在自动登录...）",
                     font=("微软雅黑", 10), fg="gray").pack()
        else:
            tk.Label(self.root, text="请输入您的名字：",
                     font=("微软雅黑", 12)).pack()

        self.e_user = tk.Entry(self.root, font=("微软雅黑", 13), width=20)
        self.e_user.pack(pady=8)
        if self.saved_user:
            self.e_user.insert(0, self.saved_user)

        tk.Button(self.root, text="进入", font=("微软雅黑", 13), width=12,
                  bg="#4CAF50", fg="white",
                  command=self.do_login).pack(pady=15)

        self.status = tk.Label(self.root, text="正在连接服务器...",
                               fg="orange", font=("微软雅黑", 10))
        self.status.pack(pady=10)

    def build_main(self):
        self.clear()
        self.room_vars.clear()
        self.grade_vars.clear()
        self.status_labels.clear()

        top = tk.Frame(self.root)
        top.pack(fill="x", padx=15, pady=6)
        tk.Label(top, text=f"欢迎，{self.username}",
                 font=("微软雅黑", 13, "bold")).pack(side="left")
        tk.Button(top, text="退出登录",
                  font=("微软雅黑", 10),
                  bg="#FF9800", fg="white",
                  command=self.do_logout).pack(side="right")

        # 显示发送者开关
        opt_row = tk.Frame(self.root)
        opt_row.pack(fill="x", padx=15, pady=2)
        tk.Checkbutton(
            opt_row, text="在大屏上显示我的名字",
            variable=self.show_sender_var,
            font=("微软雅黑", 11)
        ).pack(side="left")

        legend = tk.Frame(self.root)
        legend.pack(fill="x", padx=15)
        tk.Label(legend, text="● 在线", fg="green",
                 font=("微软雅黑", 10)).pack(side="left", padx=6)
        tk.Label(legend, text="● 离线", fg="gray",
                 font=("微软雅黑", 10)).pack(side="left", padx=6)

        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=15, pady=4)

        for g in GRADES:
            self.grade_vars[g] = tk.BooleanVar(value=False)
            frame = tk.LabelFrame(container, text="", font=("微软雅黑", 11),
                                  bd=1, relief="groove")
            frame.pack(fill="x", pady=4)

            head = tk.Frame(frame)
            head.pack(fill="x", padx=6, pady=(4, 2))
            tk.Label(head, text=g, font=("微软雅黑", 12, "bold"),
                     width=5, anchor="w").pack(side="left")
            tk.Checkbutton(head, text="全选",
                           variable=self.grade_vars[g],
                           font=("微软雅黑", 10),
                           command=lambda gg=g: self.toggle_grade(gg)).pack(side="left")

            grid = tk.Frame(frame)
            grid.pack(fill="x", padx=6, pady=(0, 6))
            for i, n in enumerate(CLASS_NUMS):
                rid = f"{g}{n}班"
                var = tk.BooleanVar(value=False)
                self.room_vars[rid] = var
                cell = tk.Frame(grid)
                cell.grid(row=i // 8, column=i % 8, padx=2, pady=1, sticky="w")
                tk.Checkbutton(cell, text=f"{n}班", variable=var,
                               font=("微软雅黑", 10)).pack(side="left")
                lab = tk.Label(cell, text="●", fg="gray",
                               font=("微软雅黑", 10))
                lab.pack(side="left")
                self.status_labels[rid] = lab

        tk.Label(self.root, text="喊话内容：",
                 font=("微软雅黑", 12)).pack(anchor="w", padx=15, pady=(8, 0))
        self.msg = tk.Text(self.root, height=5, font=("微软雅黑", 12))
        self.msg.pack(fill="x", padx=15)

        btn_row = tk.Frame(self.root)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="发送喊话", font=("微软雅黑", 13),
                  bg="#4CAF50", fg="white", width=14,
                  command=self.send).pack(side="left", padx=6)
        tk.Button(btn_row, text="全不选", font=("微软雅黑", 11),
                  command=self.clear_all).pack(side="left", padx=6)
        tk.Button(btn_row, text="只选在线", font=("微软雅黑", 11),
                  command=self.select_online).pack(side="left", padx=6)

        self.status = tk.Label(self.root, text="就绪", fg="green",
                               font=("微软雅黑", 10))
        self.status.pack(pady=4)

    def toggle_grade(self, grade):
        val = self.grade_vars[grade].get()
        for rid, var in self.room_vars.items():
            if rid.startswith(grade):
                var.set(val)

    def clear_all(self):
        for v in self.room_vars.values():
            v.set(False)
        for v in self.grade_vars.values():
            v.set(False)

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
                    self.root.after(0, lambda: self.status.config(
                        text="已连接", fg="green"))
                    if self.auto_login_pending and self.saved_user:
                        self.auto_login_pending = False
                        self.root.after(500, self._auto_login)
                    async for raw in ws:
                        msg = json.loads(raw)
                        self.root.after(0, lambda m=msg: self.handle(m))
            except Exception:
                self.ws = None
                self.root.after(0, lambda: self.status.config(
                    text="连接断开，重试中...", fg="red"))
                await asyncio.sleep(3)

    def _auto_login(self):
        if not self.ws:
            self.auto_login_pending = True
            return
        self.send_json({"action": "teacher_login",
                        "username": self.saved_user})

    def send_json(self, obj):
        if self.ws:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps(obj, ensure_ascii=False)), self.loop
            )

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
            self.status.config(text=f"已发送给 {msg.get('count',0)} 个在线班级",
                               fg="blue")
        elif t == "error":
            messagebox.showerror("错误", msg.get("msg", "未知错误"))

    def apply_status(self, online_ids):
        for rid, lab in self.status_labels.items():
            if not lab.winfo_exists():
                continue
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
        if not messagebox.askyesno("确认",
                                   "退出登录后需要重新输入名字，确定吗？"):
            return
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
