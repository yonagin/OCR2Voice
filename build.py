import os
import subprocess
import sys
import venv
import shutil

VENV_NAME = "venv"

def create_virtualenv(venv_dir):
    if os.path.exists(venv_dir):
        print(f"Virtual environment '{venv_dir}' already exists.")
        return

    print(f"Creating virtual environment '{venv_dir}'...")
    venv.create(venv_dir, with_pip=True)
    print("Virtual environment created.")


def activate_virtualenv(venv_dir):
    if os.name == 'nt':
        # Windows
        activate_script = os.path.join(venv_dir, "Scripts", "activate.bat")
    else:
        # Unix or MacOS
        activate_script = os.path.join(venv_dir, "bin", "activate")

    return activate_script



def detect_gpu(verbose=True):
    try:
        result = subprocess.run(
            ["nvidia-smi"], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True  # Only needed on Windows
        )

        if result.returncode != 0:
            if verbose:
                print("[ERROR] 'nvidia-smi' returned a non-zero exit code.")
                print("stderr:", result.stderr.strip())
            return False
        
        if verbose:
            print("[INFO] 'nvidia-smi' output:")
            print(result.stdout)
        
        return True

    except FileNotFoundError:
        if verbose:
            print("[ERROR] 'nvidia-smi' command not found. GPU likely unavailable or NVIDIA driver not installed.")
        return False
    except Exception as e:
        if verbose:
            print(f"[ERROR] Unexpected error while detecting GPU: {e}")
        return False
    
def install_dependencies(python_bin):
    print("\nInstalling PyTorch...")
    if detect_gpu():
        pip_command = [
            python_bin,
            "-m", "pip", "install", "torch==2.3.1",
            "--extra-index-url", "https://download.pytorch.org/whl/cu121"
        ]
        subprocess.check_call(pip_command)
    
    # 安装uv
    print("\nInstalling uv...")
    subprocess.check_call([
        python_bin,
        "-m", "pip", "install", "uv"
    ])

    print("\nInstalling base dependencies using uv...")
    if not os.path.exists("requirements.txt"):
        print("requirements.txt not found!")
        sys.exit(1)

    # 使用uv安装依赖，配置阿里云镜像源
    subprocess.check_call([
        python_bin,
        "-m", "uv", "pip", "install",
        "-r", "requirements.txt",
        "--index-url", "https://mirrors.aliyun.com/pypi/simple/",
         "--extra-index-url", "https://pypi.org/simple",
        "--trusted-host", "mirrors.aliyun.com"
    ])


def main():
    venv_path = os.path.abspath(VENV_NAME)
    create_virtualenv(venv_path)

    if os.name == 'nt':
        python_bin = os.path.join(venv_path, "Scripts", "python.exe")
    else:
        python_bin = os.path.join(venv_path, "bin", "python")
    
    install_dependencies(python_bin)

    # 创建一个新的Python文件来执行下载
    download_script = """
import os
from huggingface_hub import snapshot_download, HfApi
from pathlib import Path

def check_model_complete(model_path, repo_id):
    if not os.path.exists(os.path.join(model_path, "config.json")): 
        return False
        
    for endpoint in ["https://hf-mirror.com",None]:
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
             ("国内镜像源 hf-mirror.com", "https://hf-mirror.com"),
            ("官方源 Hugging Face Hub", None)
           
        ]
        
        download_successful = False
        base_patterns = [
            "*.model"
            "*.json",  
            "*.txt",   
            "*.md"     
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
"""

    # 将下载脚本写入临时文件
    with open("download_models.py", "w", encoding='utf-8') as f:
        f.write(download_script)

    # 使用虚拟环境的Python解释器运行下载脚本
    subprocess.check_call([python_bin, "download_models.py"])

    # 删除临时脚本
    os.remove("download_models.py")

    print("\nVirtual environment setup and dependencies installed successfully!")


if __name__ == "__main__":
    main()
