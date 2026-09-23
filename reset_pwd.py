import os
import sys
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog

DEFAULT_PASSWORD = "01180204"


def main():
    root = tk.Tk()
    root.withdraw()

    target_dir = filedialog.askdirectory(
        title="请选择教室电脑上的 shout 文件夹（里面应有 screen.exe）"
    )
    if not target_dir:
        root.destroy()
        return

    if not os.path.exists(os.path.join(target_dir, "screen.exe")):
        if not messagebox.askyesno("提示",
                                   "该目录下没找到 screen.exe，仍要继续吗？"):
            root.destroy()
            return

    new_pwd = simpledialog.askstring(
        "设置新密码",
        "请输入新的喊话配置密码：\n（留空则恢复默认 01180204）",
        show="*",
        parent=root
    )
    if new_pwd is None:
        root.destroy()
        return

    if new_pwd.strip() == "":
        new_pwd = DEFAULT_PASSWORD

    auth_path = os.path.join(target_dir, "auth.dat")
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
