# main_pyside.py

import sys
import os
import multiprocessing
import subprocess
import time
from PySide6.QtWidgets import QApplication

# 确保在Windows上能正确找到子进程需要的模块
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# DPI 感知设置 for PySide6 (通常Qt会自动处理)
# 在main函数中设置属性是更推荐的方式
# from PySide6.QtCore import Qt
# QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

from ocr2voice.gui_pyside import ScreenCaptureApp
from ocr2voice.ocr_service import OCRService
from ocr2voice.tts_service import TTSService

def run_tts_server(server_script_name):
    """
    在子进程中运行 FastAPI 服务。
    """
    try:
        # 使用 sys.executable 确保使用相同的 Python 解释器
        command = [sys.executable, server_script_name]
        print(f"正在启动子进程服务: {' '.join(command)}")
        # 使用 subprocess.Popen 启动，不阻塞主进程
        # 在Windows上，设置creationflags可以防止子进程弹出控制台窗口
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        
        server_process = subprocess.Popen(command, creationflags=creationflags)
        print("等待服务启动...")
        time.sleep(5)  # 等待服务器启动
        print("OCR/TTS 服务已就绪！")
        return server_process
    except FileNotFoundError:
        print(f"错误: 找不到服务脚本 '{server_script_name}'。请确保它在正确的路径下。")
        return None
    except Exception as e:
        print(f"启动服务时发生未知错误: {e}")
        return None


def main():
    """
    主函数：初始化服务和UI，并运行应用。
    """
    server_process = None
    try:
        # 1. 启动 FastAPI 服务子进程
        # 注意: multiprocessing.freeze_support() 是打包成exe时在Windows上所必需的
        multiprocessing.freeze_support()
        server_process = run_tts_server("server_fastapi.py")
        if not server_process:
            print("服务启动失败，应用即将退出。")
            return

        # 2. 初始化服务类
        ocr_service = OCRService()
        tts_service = TTSService()

        # 3. 初始化并运行 PySide6 应用
        app = QApplication(sys.argv)
        
        # 可选：启用高DPI缩放
        try:
            from PySide6.QtCore import Qt
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        except Exception as e:
            print(f"无法设置高DPI缩放: {e}")

        main_window = ScreenCaptureApp(ocr_service, tts_service)
        main_window.show()
        
        # 启动Qt事件循环
        sys.exit(app.exec())

    except Exception as e:
        print(f"应用启动失败: {e}")
        traceback.print_exc()
    finally:
        # 4. 在应用退出时，确保终止子进程
        if server_process:
            print("正在终止服务子进程...")
            server_process.terminate()
            server_process.wait() # 等待进程完全终止
            print("服务子进程已终止。")
        
        print("应用已退出。")


if __name__ == "__main__":
    # 在Windows上，对于子进程来说，__name__ == "__main__" 是必须的
    # 以防止代码被重复执行
    main()

