import argparse
from pathlib import Path
import torch
from scipy.io import wavfile
import soundfile as sf
from io import BytesIO

from tts_config import get_config
from style_bert_vits2.constants import (
    DEFAULT_ASSIST_TEXT_WEIGHT,
    DEFAULT_LENGTH,
    DEFAULT_LINE_SPLIT, 
    DEFAULT_NOISE,
    DEFAULT_NOISEW,
    DEFAULT_SDP_RATIO,
    DEFAULT_SPLIT_INTERVAL,
    DEFAULT_STYLE,
    DEFAULT_STYLE_WEIGHT,
    Languages
)
from style_bert_vits2.logging import logger
from style_bert_vits2.nlp import bert_models
from style_bert_vits2.tts_model import TTSModel, TTSModelHolder

class SB_TTS:
    def __init__(self, model_dir: str, device: str = None):
        # 初始化配置
        self.config = get_config()
        self.ln = self.config.server_config.language
        
        # 设置设备
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        # 加载BERT模型
        bert_models.load_model(Languages.JP)
        bert_models.load_tokenizer(Languages.JP)
        
        # 初始化模型持有者和加载模型
        self.model_dir = Path(model_dir)
        self.model_holder = TTSModelHolder(self.model_dir, self.device)
        self.loaded_models = self._load_models()

    def _load_models(self):
        """加载所有模型"""
        loaded_models = []
        for model_name, model_paths in self.model_holder.model_files_dict.items():
            model = TTSModel(
                model_path=model_paths[0],
                config_path=self.model_holder.root_dir / model_name / "config.json",
                style_vec_path=self.model_holder.root_dir / model_name / "style_vectors.npy",
                device=self.model_holder.device,
            )
            loaded_models.append(model)
        return loaded_models

    def infer(
        self,
        text: str,
        model_id: int = 0,
        speaker_id: int = 0,
        speaker_name: str = None,
        sdp_ratio: float = DEFAULT_SDP_RATIO,
        noise: float = DEFAULT_NOISE,
        noisew: float = DEFAULT_NOISEW,
        length: float = DEFAULT_LENGTH,
        language: Languages = None,
        auto_split: bool = DEFAULT_LINE_SPLIT,
        split_interval: float = DEFAULT_SPLIT_INTERVAL,
        assist_text: str = None,
        assist_text_weight: float = DEFAULT_ASSIST_TEXT_WEIGHT,
        style: str = DEFAULT_STYLE,
        style_weight: float = DEFAULT_STYLE_WEIGHT,
        reference_audio_path: str = None,
    ):
        """
        执行TTS推理
        返回: (采样率, 音频数据)或音频二进制数据(取决于output_format)
        """
        if language is None:
            language = self.ln
            
        if model_id >= len(
            self.model_holder.model_names
        ):
            raise_validation_error(f"model_id={model_id} not found", "model_id")
    
        model = self.loaded_models[model_id]
        
        # 处理说话人ID
        if speaker_name is not None:
            if speaker_name not in model.spk2id:
                raise ValueError(f"speaker_name={speaker_name} not found")
            speaker_id = model.spk2id[speaker_name]
        elif speaker_id not in model.id2spk:
            raise ValueError(f"speaker_id={speaker_id} not found")
            
        # 检查style
        if style not in model.style2id:
            raise ValueError(f"style={style} not found")

        # 执行推理
        sr, audio = model.infer(
            text=text,
            language=language,
            speaker_id=speaker_id,
            reference_audio_path=reference_audio_path,
            sdp_ratio=sdp_ratio,
            noise=noise,
            noise_w=noisew,
            length=length,
            line_split=auto_split,
            split_interval=split_interval,
            assist_text=assist_text,
            assist_text_weight=assist_text_weight,
            use_assist_text=bool(assist_text),
            style=style,
            style_weight=style_weight,
        )

        with BytesIO() as content:
            wavfile.write(content, sr, audio)
            return content.getvalue()

def create_sb(model_dir):
    # 初始化推理器
    sb_tts = SB_TTS(
        model_dir=model_dir,
        device= "cuda" if torch.cuda.is_available() else "cpu"
    )
    logger.info("Models loaded successfully")
    return sb_tts
    
