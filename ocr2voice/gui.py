# gui.py

import tkinter as tk
from tkinter import ttk
import traceback
import numpy as np
import cv2
from PIL import ImageGrab
import tk_async_execute as tae
import sounddevice as sd
import imagehash
import asyncio
from utils import clean_text, play_audio_nonblocking
from AppConfig import LOCAL

if LOCAL:
    from utils import local_translate as translate_text
else:
    from utils import google_translate as translate_text


class ScreenCaptureApp:
    def __init__(self, root, ocr_service, tts_service):
        self.root = root
        self.ocr_service = ocr_service
        self.tts_service = tts_service

        self.root.title("OCR to Voice")
        self.root.geometry("350x370") # Increased height for new widgets
        self.is_processing = False # 控制整体循环是否激活
        
        # 任务执行锁，防止并发冲突
        self.is_task_running = False # 控制同一时间是否已有截图识别任务在运行

        self.capture_window = None
        self.last_bbox = None
        self.instructions = "拖动选择区域 | 左键重复框选 | 右键退出"
        
        self.monitor_after_id = None
        self.last_processed_hash = None
        self.phash_threshold = 8 # 感知哈希差异阈值，可以根据需要调整

        self.border_window = None
        self.subtitle_window = None
        self.last_subtitle_pos = None

        self.monitor_interval_var = tk.IntVar(value=1)
        interval_frame = ttk.Frame(self.root)
        interval_frame.pack(pady=5)
        ttk.Label(interval_frame, text="监控间隔/s:").pack(side=tk.LEFT)
        ttk.Spinbox(interval_frame, from_=1, to=3600, textvariable=self.monitor_interval_var, width=5).pack(side=tk.LEFT)

        self.languages = {"中文": "zh", "英文": "en", "日语": "ja", "俄语":"ru", "韩语": "ko", "法语": "fr", "德语": "de", "西班牙语": "es"}
        lang_keys = list(self.languages.keys())

        # 识别语言
        source_lang_frame = ttk.Frame(self.root)
        source_lang_frame.pack(pady=5)
        ttk.Label(source_lang_frame, text="识别语言:").pack(side=tk.LEFT)
        self.source_lang_var = tk.StringVar(value="中文")
        source_lang_combo = ttk.Combobox(source_lang_frame, textvariable=self.source_lang_var, values=lang_keys, width=10, state='readonly')
        source_lang_combo.pack(side=tk.LEFT)
        self.source_lang_var.trace_add("write", self.on_source_lang_change)

        # 翻译语言
        dest_lang_frame = ttk.Frame(self.root)
        dest_lang_frame.pack(pady=5)
        ttk.Label(dest_lang_frame, text="翻译语言:").pack(side=tk.LEFT)
        self.dest_lang_var = tk.StringVar(value="日语")
        dest_lang_combo = ttk.Combobox(dest_lang_frame, textvariable=self.dest_lang_var, values=lang_keys, width=10, state='readonly')
        dest_lang_combo.pack(side=tk.LEFT)

        self.show_border_var = tk.BooleanVar(value=True)
        border_frame_check = ttk.Checkbutton(
            self.root, text="显示识别边框", variable=self.show_border_var, command=self.toggle_border_visibility
        )
        border_frame_check.pack(pady=5)

        self.translate_var = tk.BooleanVar(value=True)
        translate_check = ttk.Checkbutton(
            self.root, text="翻译识别结果", variable=self.translate_var
        )
        translate_check.pack(pady=5)
        self.tts_enabled_var = tk.BooleanVar(value=True)
        tts_check = ttk.Checkbutton(
            self.root, text="生成并播放语音", variable=self.tts_enabled_var
        )
        tts_check.pack(pady=5)

        self.start_button = ttk.Button(self.root, text="开始框选", command=self.start_capture_mode)
        self.start_button.pack(pady=10)
        self.stop_button = ttk.Button(self.root, text="停止", command=self.stop_all, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

        self.status_var = tk.StringVar(value="状态：就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

    # ---字幕创建、定位、尺寸逻辑---
    def create_subtitle_window(self, text):
        if self.subtitle_window:
            self.subtitle_window.destroy()

        self.subtitle_window = tk.Toplevel(self.root)
        self.subtitle_window.overrideredirect(True)
        self.subtitle_window.attributes("-topmost", True)
        self.subtitle_window.attributes("-alpha", 0.75)
        self.subtitle_window.config(bg='black')
        
        # 保证有 last_bbox
        if not self.last_bbox: return

        # 设置宽度与框选区域相同，高度动态
        bbox_width = self.last_bbox[2] - self.last_bbox[0]
        subtitle_label = ttk.Label(self.subtitle_window, text=text, foreground="white", background="black",
                                   font=("Arial", 14), wraplength=bbox_width - 20) # 减去padding
        subtitle_label.pack(padx=10, pady=5)

        self.subtitle_window.update_idletasks()

        # 如果用户拖动过，则使用上次的位置
        if self.last_subtitle_pos:
            x, y = self.last_subtitle_pos
            self.subtitle_window.geometry(f"+{int(x)}+{int(y)}")
        # 否则，定位到框选区域下方
        else:
            x1, y1, x2, y2 = self.last_bbox
            initial_x = x1
            initial_y = y2 + 5 # 框选区域下方5像素
            self.subtitle_window.geometry(f"+{int(initial_x)}+{int(initial_y)}")
            self.last_subtitle_pos = (initial_x, initial_y) # 存储初始位置

        subtitle_label.bind("<ButtonPress-1>", self.start_move_subtitle)
        subtitle_label.bind("<B1-Motion>", self.move_subtitle)

    def start_move_subtitle(self, event):
        self.subtitle_window.x = event.x
        self.subtitle_window.y = event.y

    def move_subtitle(self, event):
        deltax = event.x - self.subtitle_window.x
        deltay = event.y - self.subtitle_window.y
        new_x = self.subtitle_window.winfo_x() + deltax
        new_y = self.subtitle_window.winfo_y() + deltay

        if not self.last_bbox: return

        sub_width = self.subtitle_window.winfo_width()
        sub_height = self.subtitle_window.winfo_height()
        cap_x1, cap_y1, cap_x2, cap_y2 = self.last_bbox

        # 检查新位置是否与框选区域重叠
        # 如果新位置在框选区域之外，则允许移动
        is_outside = (new_x + sub_width <= cap_x1 or  # 在左侧
                      new_x >= cap_x2 or               # 在右侧
                      new_y + sub_height <= cap_y1 or  # 在上方
                      new_y >= cap_y2)                 # 在下方

        if is_outside:
            self.subtitle_window.geometry(f"+{new_x}+{new_y}")
            self.last_subtitle_pos = (new_x, new_y)

    def destroy_subtitle_window(self):
        if self.subtitle_window:
            self.subtitle_window.destroy()
            self.subtitle_window = None


    def create_border_window(self):
        if not self.show_border_var.get() or not self.last_bbox:
            return
        if self.border_window:
            self.border_window.destroy()
        x1, y1, x2, y2 = self.last_bbox
        self.border_window = tk.Toplevel()
        self.border_window.overrideredirect(True)
        self.border_window.attributes("-topmost", True)
        self.border_window.geometry(f"{x2 - x1}x{y2 - y1}+{x1}+{y1}")
        self.border_window.config(bg='lime')
        self.border_window.attributes("-transparentcolor", "white")
        inner_frame = tk.Frame(self.border_window, bg="white")
        inner_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    def toggle_border_visibility(self):
        if self.show_border_var.get():
            self.create_border_window()
        elif self.border_window:
            self.border_window.destroy()
            self.border_window = None

    def start_capture_mode(self):
        if self.is_processing or self.capture_window: return
        self.stop_button.config(state=tk.NORMAL)
        self.root.withdraw()
        self.capture_window = tk.Toplevel(self.root)
        self.capture_window.attributes("-fullscreen", True)
        self.capture_window.attributes("-alpha", 0.3)
        self.capture_window.attributes("-topmost", True)
        self.canvas = tk.Canvas(self.capture_window, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.info_text_item = self.canvas.create_text(
            self.capture_window.winfo_screenwidth() / 2, self.capture_window.winfo_screenheight() / 2,
            text=self.instructions, fill="white", font=("Arial", 20)
        )
        self.start_x = self.start_y = None
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.canvas.bind("<Button-3>", self.exit_capture_mode)

    def update_info_text(self, new_text):
        if self.capture_window and self.info_text_item:
            self.canvas.itemconfig(self.info_text_item, text=new_text)

    def on_button_press(self, event):
        if self.border_window: self.border_window.destroy(); self.border_window = None
        if self.is_processing: self.update_info_text("正在处理，请稍候..."); return
        self.update_info_text("")
        self.start_x, self.start_y = event.x, event.y
        if self.rect: self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='lime',
                                                 width=4)

    def on_mouse_drag(self, event):
        if self.rect: self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        if self.is_processing or self.capture_window is None: return
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        
        # 单击左键，使用上一个区域
        if abs(x2 - x1) < 5 and abs(y2 - y1) < 5 and self.last_bbox:
            if self.rect: self.canvas.delete(self.rect); self.rect = None
            self.toggle_border_visibility()
            self.start_processing()
            return
            
        # 区域太小
        if x2 - x1 < 10 or y2 - y1 < 10:
            self.update_info_text("区域太小，请重新拖动选择")
            if self.rect: self.canvas.delete(self.rect)
            self.capture_window.after(1500, lambda: self.update_info_text(self.instructions))
            return
            
        self.last_bbox = (x1, y1, x2, y2)
        self.last_subtitle_pos = None # 重置字幕位置，以便在下次创建时定位到新区域下方
        self.toggle_border_visibility()
        if self.rect: self.canvas.delete(self.rect); self.rect = None
        self.start_processing()

    def start_processing(self):
        if self.is_processing or not self.last_bbox: return
        self.is_processing = True
        self.stop_button.config(state=tk.NORMAL)

        if self.capture_window:
            self.capture_window.withdraw()
        self.root.deiconify()
        
        tae.async_execute(self.process_screenshot(self.last_bbox), wait=False, visible=False)

    def exit_capture_mode(self, event=None):
        if self.border_window: self.border_window.destroy(); self.border_window = None
        if self.capture_window: self.capture_window.destroy(); self.capture_window = None
        self.root.deiconify()

    def stop_all(self):
        self.is_processing = False
        self.is_task_running = False # 确保锁被重置
        
        if self.monitor_after_id:
            self.root.after_cancel(self.monitor_after_id)
            self.monitor_after_id = None
        
        try:
            sd.stop()
        except:
            pass
        
        if self.border_window: self.border_window.destroy(); self.border_window = None
        if self.capture_window: self.capture_window.destroy(); self.capture_window = None
        self.destroy_subtitle_window()
        self.root.deiconify()
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("状态：已停止")
        self.last_processed_hash = None

    def exit_app(self):
        self.stop_all()
        tae.stop()
        self.root.destroy()
        
    def on_source_lang_change(self, *args):
        """
        当识别语言 (source_lang_var) 改变时调用的回调函数。
        它会更新 OCR 服务以使用新的语言。
        """
        try:
            # 从StringVar获取新的语言名称 (e.g., "中文")
            new_lang_key = self.source_lang_var.get()
            # 从字典中查找对应的语言代码 (e.g., "zh")
            new_lang_code = self.languages[new_lang_key]
            
            # 检查 ocr_service 是否存在且有 update 方法
            if self.ocr_service and hasattr(self.ocr_service, 'update'):
                # 调用OCR服务的update方法来切换语言模型
                self.ocr_service.update(new_lang_code)
                self.status_var.set(f"状态：OCR语言已切换为 {new_lang_key}")
            else:
                # (可选) 如果服务或方法不存在，打印警告
                print("Warning: ocr_service is not available or does not have an 'update' method.")

        except Exception as e:
            # 异常处理，以防万一
            error_message = f"切换识别语言时出错: {e}"
            self.status_var.set(f"状态：{error_message}")
            traceback.print_exc()    

    async def process_screenshot(self, bbox):
        # 上锁：标记任务开始
        self.is_task_running = True
        audio_thread = None
        
        try:
            self.root.after(0, self.status_var.set, "状态：正在识别...")
            screenshot = ImageGrab.grab(bbox=bbox)
            self.last_processed_hash = imagehash.phash(screenshot)
            img_np = np.array(screenshot)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

            extracted_text = self.ocr_service.predict(img_bgr)
            if not extracted_text:
                self.root.after(0, self.status_var.set, "状态：未识别到文字，监控中...")
                return

            cleaned_text = clean_text(extracted_text).replace('\n', ' ')
            tts_input_text = cleaned_text

            if self.translate_var.get():
                self.root.after(0, self.status_var.set, "状态：正在翻译...")
                source_lang_code = self.languages[self.source_lang_var.get()]
                dest_lang_code = self.languages[self.dest_lang_var.get()]
                translated_text = translate_text(cleaned_text, source_lang_code, dest_lang_code)
                tts_input_text = translated_text
                if translated_text:
                    self.root.after(0, self.create_subtitle_window, translated_text)
            else:
                self.root.after(0, self.create_subtitle_window, cleaned_text)

            if self.tts_enabled_var.get():
                self.root.after(0, self.status_var.set, "状态：正在合成语音...")
                audio_data, samplerate = await self.tts_service.get_speech(tts_input_text)
                self.root.after(0, self.status_var.set, "状态：正在播放...")
                # 获取音频播放线程
                audio_thread = play_audio_nonblocking(audio_data, samplerate, wait=True)

        except Exception as e:
            self.is_processing = False
            self.stop_button.config(state=tk.DISABLED)
            traceback.print_exc()
            error_message = f"处理过程中发生错误: {e}"
            self.status_var.set(f"状态：{error_message}")
            self.display_error_and_reset(error_message)
        finally:
            # 如果有音频在播放，等待它完成
            if audio_thread and audio_thread.is_alive():
                # 在异步环境中等待线程完成
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, audio_thread.join)
            
            # 解锁：音频播放完成后才标记任务已结束
            self.is_task_running = False
            if self.is_processing:
                self.root.after(0, self.status_var.set, "状态：任务完成，正在监控识别区域...")
                self.root.after(100, self.start_monitoring)
                
    def start_monitoring(self):
        if not self.is_processing or not self.last_bbox: return
        if self.monitor_after_id: self.root.after_cancel(self.monitor_after_id)
        tae.async_execute(self.monitor_for_changes(), wait=False, visible=False)
    
    async def monitor_for_changes(self):
        if not self.is_processing: return

        if self.is_task_running:
            interval_ms = self.monitor_interval_var.get() * 1000
            self.monitor_after_id = self.root.after(interval_ms, self.start_monitoring)
            return

        try:
            screenshot = ImageGrab.grab(bbox=self.last_bbox)
            current_hash = imagehash.phash(screenshot)
            hash_diff = current_hash - self.last_processed_hash

            if hash_diff > self.phash_threshold:
                self.root.after(0, self.status_var.set, "状态：检测到内容变化，开始新任务...")
                if not self.is_task_running:
                    tae.async_execute(self.process_screenshot(self.last_bbox), wait=False, visible=False)
            else:
                interval_ms = self.monitor_interval_var.get() * 1000
                self.monitor_after_id = self.root.after(interval_ms, self.start_monitoring)

        except Exception as e:
            print(f"监控时发生错误: {e}")
            interval_ms = self.monitor_interval_var.get() * 1000
            self.monitor_after_id = self.root.after(interval_ms, self.start_monitoring)

    def display_error_and_reset(self, message):
        self.is_processing = False
        self.is_task_running = False # 确保锁被重置
        self.stop_button.config(state=tk.DISABLED)

        if self.capture_window:
            self.update_info_text(message)
            self.capture_window.deiconify()
            self.capture_window.after(3000, lambda: self.update_info_text(self.instructions))
        else:
            self.root.deiconify()
