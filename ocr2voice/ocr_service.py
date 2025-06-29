# ocr_service.py

import sys
from paddleocr import PaddleOCR
import os
import tarfile
from utils import download_OCR

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

class OCRService:
    def __init__(self, OCR_LANGUAGE):
        """
        初始化OCR服务，加载PaddleOCR模型。
        """
        self.ocr_engine = self._initialize_ocr(OCR_LANGUAGE)
        self.use_predict = hasattr(self.ocr_engine, 'predict')  # 判断是否支持 predict
        self.current_lang = OCR_LANGUAGE

    @staticmethod
    def _initialize_ocr(OCR_LANGUAGE):
        """
        加载OCR模型，如果默认不支持则自动下载
        """
        LANG_CODE_MAP = {
            'zh':'ch',
            'ja': 'japan',
            'ko': 'korean',
            'de': 'german',
        }
        # 获取 PaddleOCR 需要的真实语言代码
        paddle_lang_code = LANG_CODE_MAP.get(OCR_LANGUAGE, OCR_LANGUAGE)
        print("正在加载 OCR 模型，请稍候...")
        try:
            # 尝试初始化OCR引擎
            engine = PaddleOCR(use_textline_orientation=True, lang=paddle_lang_code)
            print("OCR 模型加载完成。")
            return engine
        except Exception as e:
            print(f"默认模型不支持语言 {OCR_LANGUAGE}，尝试下载专用模型...")
            try:
                # 下载并加载专用模型
                model_dir = download_OCR(OCR_LANGUAGE)
                engine = PaddleOCR(
                    use_textline_orientation=True,
                    lang=paddle_lang_code,
                    rec_model_dir=model_dir
                )
                print(f"{OCR_LANGUAGE} 语言模型下载并加载完成。")
                return engine
            except Exception as download_error:
                print(f"错误：无法初始化 {OCR_LANGUAGE} OCR 模型。错误信息: {download_error}")
                sys.exit(1)

    def predict(self, image_np):
        """
        从图像中识别文字，兼容不同版本 API（predict / ocr）。
        """
        extracted_text = ""

        if self.use_predict:
            # 新版本使用 predict 方法
            result = self.ocr_engine.predict(image_np)
            if result and isinstance(result[0], dict) and 'rec_texts' in result[0]:
                texts = result[0]['rec_texts']
                extracted_text = "\n".join(texts)
        else:
            # 旧版本使用 ocr 方法
            result = self.ocr_engine.ocr(image_np, cls=True)
            if result and result[0]:
                all_texts = []
                for i in range(len(result[0])):
                    text = result[0][i][1][0]
                    all_texts.append(text)
                extracted_text = "\n".join(all_texts)

        print(f"识别到的原文:\n{extracted_text}")
        return extracted_text

    def update(self, source_lang):
        """
        更新OCR引擎使用的语言
        """
        if source_lang != self.current_lang:
            self.current_lang = source_lang
            self.ocr_engine = self._initialize_ocr(source_lang)
            self.use_predict = hasattr(self.ocr_engine, 'predict')