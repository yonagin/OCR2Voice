# OCR2Voice 多语言翻译工具  

基于 Tkinter 的图形界面，支持本地 OCR 文字识别、多语言翻译及语音合成（TTS）。  

## 功能  
- **OCR**: 从图片或截图中提取文字。  
- **翻译**: 支持多语言翻译（离线或在线 API 模式）。  
- **语音合成**: 将翻译结果转为语音（默认使用本地 Style-Bert-VITS2 模型，可切换为外部 API）。  
- **友好界面**: 使用 Tkinter 构建的简易图形界面。  

## 环境要求  
- Python 3.10 或更高版本  
- Windows 系统（已在 Win10/11 测试）  

## 快速开始（Windows）  
1. **克隆仓库**:  
   ```bash  
   git clone https://github.com/yonagin/OCR2Voice.git
   cd OCR2Voice 
   ```  

2. **初始化环境 & 下载模型**:  
   - 双击 **`build.bat`** 自动创建虚拟环境并下载模型。  
     - *注：模型下载可能较慢，若 CMD 窗口卡顿，按 `空格键` 可继续执行。*  

3. **运行程序**:  
   - 完成后双击 **`run.bat`** 启动应用。  

## 配置选项  
编辑 **`AppConfig.py`** 文件以自定义功能：  
- **翻译模式**:  
  - 设置 `LOCAL = False` 可禁用离线翻译，改用在线 API。  
- **语音合成引擎**:  
  - 默认使用本地 **Style-Bert-VITS2**（集成源码）。  
  - 切换为 API 模式：  
    1. 设置 `API_INFER = True`。  
    2. 修改 `API_URL` 为你的服务地址（API 格式参考 **`server_fastapi.py`**）。  

## 注意事项  
- 离线模型需占用较大存储空间和内存。  
- API 模式下请确保服务可用且配置正确。
