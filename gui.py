import tkinter as tk
from tkinter import ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk
from  ZipWriteLogic import process_entry_point
from  ZipDeleteLogic import remove_white_pages_entry_point
import threading

def handle_drop(event):
    # event.data 是一个包含所有文件路径的字符串，使用 tk.splitlist分割
    file_paths = root.tk.splitlist(event.data)
    for file_path in file_paths:
        file_listbox.insert(tk.END, file_path)
    file_listbox.yview_moveto(1.0) 
    
def run_processing_thread(paths):
    try:
        process_entry_point(paths, logger=log_message)
    except Exception as e:
        log_message(f"发生严重错误: {e}")# 捕获任何未预料的全局错误
        import traceback
        log_message(traceback.format_exc())
    finally:
        log_message("="*20)#重新启用按钮
        log_message("任务处理结束。")
        log_message("="*20)
        button1.config(state=tk.NORMAL)
        button2.config(state=tk.NORMAL)
        button3.config(state=tk.NORMAL)
        
def run_processing_thread2(paths, entry_point_func, task_name):
    try:
        # 调用传入的特定功能函数
        entry_point_func(paths, logger=log_message)
    except Exception as e:
        # 捕获任何未预料的全局错误
        log_message(f"任务 '{task_name}' 发生严重错误: {e}")
        import traceback
        log_message(traceback.format_exc())
    finally:
        # 任务完成后，无论成功或失败，都重新启用按钮
        log_message("="*20)
        log_message(f"任务 '{task_name}' 处理结束。")
        log_message("="*20)
        button1.config(state=tk.NORMAL)
        button2.config(state=tk.NORMAL)
        button3.config(state=tk.NORMAL)
        
def button1_action():
    file_paths = file_listbox.get(0, tk.END)
    if not file_paths:
        log_message("文件列表为空，请先拖入文件或文件夹。")
        return
    button1.config(state=tk.DISABLED)#阻塞时禁用按钮
    button2.config(state=tk.DISABLED)
    button3.config(state=tk.DISABLED)
    log_message("="*20)
    log_message("任务已开始，处理中请稍候...")
    log_message("="*20)
    #创建并启动一个后台线程来执行 process_entry_point
    thread = threading.Thread(
        target=run_processing_thread, 
        args=(file_paths,)
    )
    thread.daemon = True  # 设置为守护线程，主窗口关闭时线程也会退出
    thread.start()

def button2_action():
    file_paths = file_listbox.get(0, tk.END)
    if not file_paths:
        log_message("文件列表为空，请先拖入文件或文件夹。")
        return
    button1.config(state=tk.DISABLED)#阻塞时禁用按钮
    button2.config(state=tk.DISABLED)
    button3.config(state=tk.DISABLED)
    log_message("="*20)
    log_message("【删除白页】任务已开始...")
    log_message("="*20)
    thread = threading.Thread(
        target=run_processing_thread2, 
        args=(file_paths, remove_white_pages_entry_point, "【删除白页】")
    )
    thread.daemon = True
    thread.start()
    
def button3_action():
    log_message("正在清空文件列表")
    file_listbox.delete(0, tk.END)
    log_message("文件列表已清空。")
    
def log_message(message):
    """向底部的日志文本框中添加一条消息"""
    try:
        log_text.config(state=tk.NORMAL)  
        log_text.insert(tk.END, message + "\n")
        log_text.config(state=tk.DISABLED) # 重新锁定，设为只读
        log_text.yview_moveto(1.0) # log_text文本框滚动，0为顶部、1为底部
        root.update_idletasks()  # 强制更新UI
    except Exception as e:
        print(f"日志输出错误: {e}")

# 主程序
if __name__ == "__main__":
    root = TkinterDnD.Tk()
    root.title("跨页修正")
    root.geometry("600x480")
    
    icon_path = 'icon.png'
    
    try:
        image = Image.open(icon_path)
        photo_image = ImageTk.PhotoImage(image)
        root.iconphoto(True, photo_image)
    except Exception as e:
        print(f"设置图标时出错: {e}")
    
    #顶部框架
    top_frame = ttk.Frame(root, padding=5)
    top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
    #左侧拖放区
    drop_zone_frame = ttk.LabelFrame(top_frame)
    drop_zone_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    drop_label = ttk.Label(drop_zone_frame, text="请将文件拖拽到此处（仅支持zip）",  anchor="center")
    drop_label.pack(fill=tk.BOTH, expand=True)
    drop_label.drop_target_register(DND_FILES)
    drop_label.dnd_bind('<<Drop>>', handle_drop)
    
    #右侧文件列表区
    file_list_frame = ttk.LabelFrame(top_frame, text=" 已选中的文件 ", padding=5)
    file_list_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    
    #滚动条
    list_scrollbar = ttk.Scrollbar(file_list_frame, orient=tk.VERTICAL)
    #列表框
    file_listbox = tk.Listbox(file_list_frame, yscrollcommand=list_scrollbar.set, selectmode=tk.EXTENDED)
    list_scrollbar.config(command=file_listbox.yview)
    list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    #按钮框架
    middle_frame = ttk.Frame(root, padding=(10, 0, 10, 0))
    middle_frame.pack(side=tk.TOP, fill=tk.X)
    
    #分隔线
    separator = ttk.Separator(middle_frame, orient='horizontal')
    separator.pack(fill='x', pady=5)
    
    # 按钮容器
    button_container = ttk.Frame(middle_frame)
    button_container.pack(side=tk.RIGHT)
    button1 = ttk.Button(button_container, text="加入扉页", command=button1_action)
    button1.pack(side=tk.LEFT, padx=5)
    button2 = ttk.Button(button_container, text="删除扉页", command=button2_action)
    button2.pack(side=tk.LEFT, padx=5)
    button3 = ttk.Button(button_container, text="清空文件列表", command=button3_action)
    button3.pack(side=tk.LEFT, padx=5)
    
    #底部框架
    bottom_frame = ttk.LabelFrame(root)
    bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
    
    #滚动条
    log_scrollbar = ttk.Scrollbar(bottom_frame, orient=tk.VERTICAL)
    #文本框
    log_text = tk.Text(bottom_frame, wrap=tk.WORD, yscrollcommand=log_scrollbar.set, state=tk.DISABLED)
    log_scrollbar.config(command=log_text.yview)
    log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    log_message("程序已启动，等待操作。")
    root.mainloop()