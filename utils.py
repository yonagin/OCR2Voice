# utils.py

import re
import os
import tarfile
from pathlib import Path
from tqdm import tqdm
import threading
import requests
import numpy as np
import sounddevice as sd
from googletrans import Translator
import subprocess  
import sys
import time


#翻译参数, 如果硬件更好，可以尝试 'facebook/nllb-200-1.3B' 或 'facebook/nllb-200-3.3B' 以获得更高质量
translator = None
model_lock = threading.Lock()
tokenizer = None
model = None
NLLB_LANG_MAP = {
    'en': 'eng_Latn',
    'zh': 'zho_Hans',  
    'ja': 'jpn_Jpan',
    'ko': 'kor_Hang',
    'fr': 'fra_Latn',
    'de': 'deu_Latn',
    'es': 'spa_Latn',
    'ru': 'rus_Cyrl',
}

#OCR语言模型模型映射表
MODEL_URLS = {
    'zh': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/chinese/ch_PP-OCRv3_rec_infer.tar',
    'en': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/latin_PP-OCRv3_rec_infer.tar',
    'fr': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/french_PP-OCRv3_rec_infer.tar',
    'de': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/german_PP-OCRv3_rec_infer.tar',
    'ja': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/japan_PP-OCRv3_rec_infer.tar',
    'ko': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/korean_PP-OCRv3_rec_infer.tar',
    'it': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/italian_PP-OCRv3_rec_infer.tar',
    'es': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/spanish_PP-OCRv3_rec_infer.tar',
    'pt': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/portuguese_PP-OCRv3_rec_infer.tar',
    'ru': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/russian_PP-OCRv3_rec_infer.tar',
    'uk': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/ukranian_PP-OCRv3_rec_infer.tar',
    'be': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/belarusian_PP-OCRv3_rec_infer.tar',
    'te': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/te_PP-OCRv3_rec_infer.tar',
    'sa': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/saudi_arabia_PP-OCRv3_rec_infer.tar',
    'ta': 'https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/ta_PP-OCRv3_rec_infer.tar',
}

def download_OCR(lang: str):
    """
    下载并解压指定语言的OCR模型，并显示下载和解压进度条。

    Args:
        lang (str): 要下载的语言模型的键名 (例如 'ch_PP-OCRv4').

    Returns:
        str: 解压后模型的目录路径。
    """
    if lang not in MODEL_URLS:
        raise ValueError(f"语言 '{lang}' 不在支持的列表中。可用模型: {list(MODEL_URLS.keys())}")

    model_url = MODEL_URLS[lang]
    model_name = os.path.basename(model_url)
    model_dir = Path("model_assets") / lang
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / model_name
    extracted_folder_path = model_dir / model_name.replace('.tar', '')
    
    key_model_file = extracted_folder_path / "inference.pdmodel"
    if extracted_folder_path.is_dir() and key_model_file.exists():
        print(f"语言模型 '{lang}' 已存在于: {extracted_folder_path}")
        print("跳过下载和解压。")
        return str(extracted_folder_path)
    
    try:
        print(f"开始下载 {lang} 语言模型...")
        response = requests.get(model_url, stream=True)
        response.raise_for_status()

        # 获取文件总大小，用于tqdm计算进度
        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kibibyte

        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True, desc=f"正在下载 {model_name}")
        
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=block_size):
                progress_bar.update(len(chunk))
                f.write(chunk)
        
        progress_bar.close()

        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            print("错误：下载的文件大小与预期不符。")
            return None

    except requests.exceptions.RequestException as e:
        print(f"下载失败: {e}")
        return None

    print(f"正在解压 {model_name}...")
    try:
        with tarfile.open(model_path, 'r') as tar:
            # 获取所有成员，以便为 tqdm 设置 total
            members = tar.getmembers()
            
            # 使用 tqdm 包装 tar.extractall 的迭代过程
            for member in tqdm(iterable=members, total=len(members), desc=f"正在解压到 {model_dir}"):
                tar.extract(member=member, path=model_dir)

    except tarfile.TarError as e:
        print(f"解压失败: {e}")
        return None
    finally:
        os.remove(model_path)
        pass

    print(f"模型已成功下载并解压到: {extracted_folder_path}")
    return str(extracted_folder_path)
    

def clean_text(text):
    """
    清理文本，只保留中文字符、字母、数字和常见标点。
    """
    # 正则表达式与原始脚本保持一致
    return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、：；“”‘’（）《》【】]', '', text)

def google_translate(text,src_lang: str, dest_lang: str):
    """
    使用googletrans将文本翻译成目标语言。
    """
    global translator
    if not text:
        return ""
    if not translator:
        translator = Translator()
    # 使用配置文件中指定的目标语言
    translated = translator.translate(text, dest=dest_lang)
    print(f"翻译结果: {translated.text}")
    return translated.text


def local_translate(text: str, 
    src_lang: str, 
    dest_lang: str,
    model_path: str = "./model_assets/nllb-200-distilled-600M",
):
    """
    使用本地 Transformers (NLLB 模型) 将文本从源语言翻译成目标语言。

    Args:
        text (str): 需要翻译的文本。
        src_lang (str): 源语言代码 (例如 'zh' for Chinese, 'en' for English)。
        dest_lang (str): 目标语言代码 (例如 'en' for English, 'zh' for Chinese)。

    Returns:
        str: 翻译后的文本。
    """
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    global tokenizer, model
    
        
    if not text:
        return ""
        
    # --- 检查并加载模型 (线程安全) ---
    with model_lock:
        if tokenizer is None or model is None:
            print(f"正在从{model_path}加载本地翻译模型...")
            
            try:
                # 确定运行设备：优先使用GPU
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"模型将运行在: {device.upper()}")

                tokenizer = AutoTokenizer.from_pretrained(
                    model_path, 
                    src_lang=NLLB_LANG_MAP[src_lang]
                )
                model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(device)
                print("模型加载成功！")

            except Exception as e:
                print(f"模型加载失败: {e}")
                return "[模型加载错误]"

    try:
        # --- 执行翻译 ---
        # 从映射中获取NLLB专用的语言代码
        src_code = NLLB_LANG_MAP.get(src_lang)
        dest_code = NLLB_LANG_MAP.get(dest_lang)

        if not src_code or not dest_code:
            raise ValueError(f"不支持的语言代码。源: {src_lang}, 目标: {dest_lang}")

        # 更新分词器的源语言
        tokenizer.src_lang = src_code
        
        # 将文本编码为模型输入
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        # 生成翻译结果，强制解码器以目标语言ID开始
        translated_tokens = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.lang_code_to_id[dest_code],
            num_beams=5,
            early_stopping=True,
            repetition_penalty=1.3,
            max_length=1024 # 可以根据需要调整最大长度
        )

        # 解码得到最终文本
        translated_text = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        
        print(f"翻译结果: {translated_text}")
        return translated_text

    except Exception as e:
        print(f"翻译过程中出现错误: {e}")
        return "[翻译错误]"


def run_tts(script_name):
    """
    在子进程中运行tts脚本。
    """
    command = [sys.executable, script_name]
    print(f"正在启动子进程，使用解释器: {sys.executable}")
    subprocess.Popen(command)
    
def play_audio_nonblocking(data, samplerate, wait=False):
    """
    在单独的线程中非阻塞地播放音频。
    如果 wait=True，返回线程对象以便等待完成。
    """
    def play():
        try:
            # 确保数据类型正确
            audio_data = data.astype(np.float32)
            with sd.OutputStream(samplerate=samplerate, channels=audio_data.shape[1] if audio_data.ndim > 1 else 1) as stream:
                stream.write(audio_data)
        except Exception as e:
            print(f"播放音频时出错: {e}")

    # 创建并启动守护线程来播放音频
    thread = threading.Thread(target=play, daemon=True)
    thread.start()
    
    if wait:
        return thread
