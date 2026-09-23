import os
import sys
import tkinter as tk
from tkinter import simpledialog, messagebox

DEFAULT_PASSWORD = "01180204"
DATA_DIR = r"C:\ClassroomShout"


def ensure_data_dir():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception as e:
        print("创建数据目录失败:", e)


def main():
    root = tk.Tk()
    root.withdraw()

    ensure_data_dir()

    new_pwd = simpledialog.askstring(
        "设置新密码",
        f"将修改：{DATA_DIR}\\auth.dat\n\n"
        "请输入新的喊话配置密码：\n（留空则恢复默认 01180204）",
        show="*",
        parent=root
    )
    if new_pwd is None:
        root.destroy()
        return

    if new_pwd.strip() == "":
        new_pwd = DEFAULT_PASSWORD

    auth_path = os.path.join(DATA_DIR, "auth.dat")
    try:
        with open(auth_path, "w", encoding="utf-8") as f:
            f.write(new_pwd)
        messagebox.showinfo(
            "完成",
            f"密码已更新为：{new_pwd}\n\n"
            f"保存位置：{auth_path}\n\n"
            f"新密码立即生效（无需重启 screen.exe）。"
        )
    except Exception as e:
        messagebox.showerror("错误", f"写入失败：{e}")

    root.destroy()


if __name__ == "__main__":
    main()
