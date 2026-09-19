import asyncio
import json
import threading
import tkinter as tk
from tkinter import messagebox
import websockets

SERVER = "wss://shout-server-production.up.railway.app"

GRADES = ["高一", "高二", "高三"]
CLASS_NUMS = list(range(1, 17))


class TeacherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("办公室喊话")
        self.root.geometry("760x720")

        self.ws = None
        self.loop = None
        self.username = None
        self.room_vars = {}
        self.grade_vars = {}

        threading.Thread(target=self.connect, daemon=True).start()
        self.build_login()
        self.root.mainloop()

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def build_login(self):
        self.clear()
        self.username = None
        self.room_vars.clear()
        self.grade_vars.clear()

        tk.Label(self.root, text="办公室喊话",
                 font=("微软雅黑", 20, "bold")).pack(pady=25)
        tk.Label(self.root, text="请输入您的名字：",
                 font=("微软雅黑", 12)).pack()
        self.e_user = tk.Entry(self.root, font=("微软雅黑", 13), width=20)
        self.e_user.pack(pady=8)
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

        top = tk.Frame(self.root)
        top.pack(fill="x", padx=15, pady=6)
        tk.Label(top, text=f"欢迎，{self.username}",
                 font=("微软雅黑", 13, "bold")).pack(side="left")
        tk.Button(top, text="退出登录",
                  font=("微软雅黑", 10),
                  bg="#FF9800", fg="white",
                  command=self.do_logout).pack(side="right")

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
                key = (g, n)
                var = tk.BooleanVar(value=False)
                self.room_vars[key] = var
                tk.Checkbutton(grid, text=f"{n}班", variable=var,
                               font=("微软雅黑", 10), width=5).grid(
                    row=i // 8, column=i % 8, padx=2, pady=1, sticky="w")

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

        self.status = tk.Label(self.root, text="就绪", fg="green",
                               font=("微软雅黑", 10))
        self.status.pack(pady=4)

    def toggle_grade(self, grade):
        val = self.grade_vars[grade].get()
        for (g, n), var in self.room_vars.items():
            if g == grade:
                var.set(val)

    def clear_all(self):
        for v in self.room_vars.values():
            v.set(False)
        for v in self.grade_vars.values():
            v.set(False)

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
                    async for raw in ws:
                        msg = json.loads(raw)
                        self.root.after(0, lambda m=msg: self.handle(m))
            except Exception:
                self.ws = None
                self.root.after(0, lambda: self.status.config(
                    text="连接断开，重试中...", fg="red"))
                await asyncio.sleep(3)

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
        elif t == "sent":
            self.status.config(text=f"已发送给 {msg.get('count',0)} 个在线班级",
                               fg="blue")
        elif t == "error":
            messagebox.showerror("错误", msg.get("msg", "未知错误"))

    def do_login(self):
        name = self.e_user.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入名字")
            return
        self.send_json({"action": "teacher_login", "username": name})

    def do_logout(self):
        if not messagebox.askyesno("确认", "退出登录后需要重新输入名字，确定吗？"):
            return
        self.username = None
        self.build_login()

    def send(self):
        text = self.msg.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("提示", "请输入喊话内容")
            return
        targets = []
        for (g, n), var in self.room_vars.items():
            if var.get():
                targets.append(f"{g}{n}班")
        if not targets:
            messagebox.showwarning("提示", "请先勾选至少一个班级")
            return
        self.send_json({"action": "shout",
                        "room_ids": targets, "text": text})
        self.msg.delete("1.0", "end")


if __name__ == "__main__":
    TeacherApp()
