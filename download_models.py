
import os
from huggingface_hub import snapshot_download, HfApi
from pathlib import Path

def check_model_complete(model_path, repo_id):
    if not os.path.exists(os.path.join(model_path, "config.json")): 
        return False
        
    for endpoint in [None, "https://hf-mirror.com"]:  # 先主站，后镜像
        try:
            api = HfApi(endpoint=endpoint)
            repo_files = api.list_repo_files(repo_id=repo_id, repo_type="model")
            if not os.path.exists(model_path):
                print(f"本地路径不存在: {model_path}")
                return False
            local_files = set(os.listdir(model_path))
            missing = [f for f in repo_files if f not in local_files]
            if missing:
                print(f"缺失 {len(missing)} 个文件: {missing[:10]}")
                return False
            print("模型文件完整！")
            return True
        except Exception as e:
            print(f"访问 {'镜像' if endpoint else '主站'} 失败: {e}")
    return False


def download_from_hf(model_path,repo_id, model_patterns=["*.bin"]):
    if not check_model_complete(model_path, repo_id):
        print(f"本地模型未在 '{model_path}' 找到。")
        endpoints_to_try = [
            ("官方源 Hugging Face Hub", None),
            ("国内镜像源 hf-mirror.com", "https://hf-mirror.com")
        ]
        
        download_successful = False
        base_patterns = [
            "*.json",  # 配置文件
            "*.txt",   # 必要的文本文件
            "*.md"     # 说明文件
        ]
        
        allow_patterns = base_patterns + model_patterns
        
        for name, endpoint in endpoints_to_try:
            print(f"--> 正在尝试从 [{name}] 下载模型...")
            try:
                snapshot_download(
                    repo_id=repo_id,
                    local_dir=model_path,
                    allow_patterns=allow_patterns,
                    local_dir_use_symlinks=False,
                    resume_download=True,
                    endpoint=endpoint,
                )
                print(f"√ 模型从 [{name}] 下载成功！")
                download_successful = True
                break
            except Exception as e:
                print(f"X 从 [{name}] 下载失败。")
                if "ConnectionError" in str(e) or "Timeout" in str(e):
                    print("   错误详情: 网络连接超时。")
                else:
                    print(f"   错误详情: {e}")
                last_error = e
        
        if not download_successful:
            error_message = f"所有下载源（包括官方和镜像）均尝试失败。请检查您的网络连接或代理设置。"
            print(error_message)
            return f"[{error_message}]"

download_from_hf("./model_assets/nllb-200-distilled-600M","facebook/nllb-200-distilled-600M")
download_from_hf("./bert/deberta-v2-large-japanese-char-wwm","ku-nlp/deberta-v2-large-japanese-char-wwm")
download_from_hf("./model_assets/voice_model","elixirx/style_bert_vits2_girl",["*.safetensors","*.npy"])
