import tkinter as tk
import tk_async_execute as tae
import multiprocessing
import time
import os
from AppConfig import API_INFER, OCR_LANGUAGE, API_URL, TTS_MODEL_ID, SPEAKER_ID, API_TIMEOUT
from utils import run_tts
from sb_tts import create_sb

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# DPI 感知设置，与原始脚本一致
try:
    import ctypes

    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception as e:
        print(f"警告: 无法设置 DPI 感知。错误: {e}")

from ocr2voice.gui import ScreenCaptureApp
from ocr2voice.ocr_service import OCRService
from ocr2voice.tts_service import TTSService

def main():
    """
    主函数：初始化服务和UI，并运行应用。
    """
    try:
        # 初始化服务
        ocr_service = OCRService(OCR_LANGUAGE)
        
        if API_INFER:
            parallel_process = multiprocessing.Process(target=run_tts,args=("server_fastapi.py",))
            parallel_process.start()
            tts_service = TTSService(API_URL, TTS_MODEL_ID, SPEAKER_ID, API_TIMEOUT)
        else:
            sb_tts = create_sb("./model_assets")
            tts_service = TTSService(API_URL, TTS_MODEL_ID, SPEAKER_ID, API_TIMEOUT, sb_tts)


        # 初始化并运行 tk_async_execute
        tae.start()

        # 创建Tkinter主窗口并启动应用
        root = tk.Tk()
        app = ScreenCaptureApp(root, ocr_service, tts_service)
        root.mainloop()

    except Exception as e:
        print(f"应用启动失败: {e}")
    finally:
        # 确保在退出时停止异步任务执行器
        tae.stop()
        # 如果需要，也可以在这里终止并行进程
        if 'parallel_process' in locals():
            parallel_process.terminate()


if __name__ == "__main__":
    main()
