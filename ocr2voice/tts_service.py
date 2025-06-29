import asyncio
import io
import requests
import soundfile as sf
import numpy as np  # soundfile 通常返回 numpy 数组
from typing import Tuple
from AppConfig import API_INFER

class TTSService:
    """
    一个封装了 VITS TTS API 的服务类。

    该类负责将文本转换为语音波形数据。
    配置参数在实例化时传入。

    Attributes:
        api_url (str): VITS API 的 endpoint URL。
        model_id (int): 使用的 TTS 模型 ID。
        speaker_id (int): 使用的说话人 ID。
        timeout (int): API 请求的超时时间（秒）。
    """
    
    def __init__(self, 
                 api_url: str, 
                 model_id: int = 0, 
                 speaker_id: int = 0, 
                 timeout: int = 60,
                 sb_tts = None):
        self.api_url = api_url
        self.model_id = model_id
        self.speaker_id = speaker_id
        self.timeout = timeout
        self.sb_tts = sb_tts
        print(f"TTS 服务已初始化")

    async def get_speech(self, text: str) -> Tuple[np.ndarray, int]:
        """
        异步调用 VITS API 将文本转换为语音并返回音频数据。

        Args:
            text (str): 需要转换的文本。

        Returns:
            Tuple[np.ndarray, int]: 一个元组，包含音频数据 (numpy 数组) 和采样率 (整数)。

        Raises:
            Exception: 如果 API 请求或音频处理失败。
        """
        # 使用实例属性来构建请求参数
        params = {
            'text': text,

        }
        
        try:
            if API_INFER:
                # 异步执行阻塞的网络请求
                response = await asyncio.to_thread(
                    requests.get, self.api_url, params=params, timeout=self.timeout
                )
                response.raise_for_status()  # 如果状态码不是 2xx，则引发 HTTPError

                # 从响应内容中异步读取音频数据
                with io.BytesIO(response.content) as f:
                    data, samplerate = sf.read(f)
                    
            else:
                content = self.sb_tts.infer(text,model_id=self.model_id,speaker_id=self.speaker_id)
                with io.BytesIO(content) as f:
                    data, samplerate = sf.read(f)
                    
            print("语音数据获取成功。")
            return data, samplerate
        
        except requests.exceptions.RequestException as e:
            # 更具体的异常捕获
            print(f"错误: API 请求失败 - {e}")
            raise Exception(f"API 请求失败: {e}") from e
        except Exception as e:
            # 捕获其他可能的错误，例如 soundfile 读取失败
            print(f"错误: 音频处理失败 - {e}")
            raise Exception(f"音频处理失败: {e}") from e
            
