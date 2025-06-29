# config.py

"""
应用程序的全局配置文件。

该文件用于集中管理所有可配置的常量和参数，例如第三方服务的API地址、
模型ID、语言设置等。将配置与代码分离，便于未来的修改和维护。
"""

# VITS (文本到语音) API 配置
API_INFER = False
API_URL = "http://127.0.0.1:5000/voice"
TTS_MODEL_ID = 0  # 使用的语音模型ID
SPEAKER_ID = 0  # 使用的说话人ID
API_TIMEOUT = 60  # API请求超时时间（秒）

# OCR (光学字符识别) 配置
OCR_LANGUAGE = 'ch'  # 指定OCR引擎识别的语言，'ch'代表中英文混合

# 翻译配置
LOCAL = True #使用本地翻译模型
