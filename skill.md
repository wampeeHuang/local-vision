---
name: local-vision
category: 开发与工具
description: 本地视觉增强。四引擎视觉理解（MiniCPM-V粗扫/Qwen3-VL-8B精读/GLM-4.6V云端/Tesseract OCR），为纯文本模型提供外置眼睛。适用：读图、OCR、截图理解、产品图分析。
---

# 本地视觉增强

DeepSeek v4 Pro API 不能直接看图片。本 skill 用外部视觉模型做外置眼睛。

## 决策树

```
需要做什么？
├── 提取图片中的文字（清晰印刷体）→ Tesseract OCR（<1s，不占显存）
├── 理解图片内容/场景/产品 → MiniCPM-V 4.6（首选粗扫，免费本地 2-10s）
├── 精确 OCR / 空间关系 / 时间戳定位 / 复杂推理 → Qwen3-VL-8B（精读复核，本地 5-20s）
└── 显存被 ComfyUI/SD 占满，或两本地引擎都不想启动 → GLM-4.6V（云端，3-10s，限速）
```

**分工原则：** 批量图/全片扫用 MiniCPM-V（轻快），候选结果复核用 Qwen3-VL（准）。两模型同目录不同端口，API 格式完全相同。

**NOT for：** 生成图片 → ComfyUI / aigoapi gpt-image-2

## 引擎一：MiniCPM-V 4.6（本地主力）

OpenAI 兼容 API，推理速度 ~290 t/s GPU。

### 启动

```powershell
Start-Process -NoNewWindow -FilePath "D:\tools\MiniCPM-V\llama-server.exe" `
  -ArgumentList "-m", "MiniCPM-V-4_6-Q4_K_M.gguf", "--mmproj", "mmproj-MiniCPM-V-4_6-f16.gguf", `
  "--port", "8080", "--host", "127.0.0.1", "-ngl", "99" `
  -WorkingDirectory "D:\tools\MiniCPM-V"
```

### 健康检查

```bash
curl http://127.0.0.1:8080/health
# → {"status":"ok"}
```

### API 调用

**端点：** `POST http://127.0.0.1:8080/v1/chat/completions`

```python
import urllib.request, json, base64

def minicpm_vision(image_path, prompt="描述这张图片的内容。用中文回答。"):
    img_b64 = base64.b64encode(open(image_path, 'rb').read()).decode()
    body = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }],
        "max_tokens": 600
    }
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"]
```

**PowerShell 版本：**

```powershell
$imgBytes = [System.IO.File]::ReadAllBytes("图片路径")
$imgB64 = [Convert]::ToBase64String($imgBytes)
$body = @{
    messages = @(@{role="user"; content=@(
        @{type="image_url"; image_url=@{url="data:image/jpeg;base64,$imgB64"}},
        @{type="text"; text="你的问题"}
    )})
    max_tokens = 600
} | ConvertTo-Json -Depth 6
$bodyBytes = [Text.Encoding]::UTF8.GetBytes($body)
$req = [Net.HttpWebRequest]::Create("http://127.0.0.1:8080/v1/chat/completions")
$req.Method = "POST"; $req.ContentType = "application/json"; $req.Timeout = 120000
$req.GetRequestStream().Write($bodyBytes, 0, $bodyBytes.Length)
$reader = New-Object IO.StreamReader($req.GetResponse().GetResponseStream())
$reader.ReadToEnd(); $reader.Close()
```

### 关闭

```bash
npx kill-port 8080
# 或 PowerShell: Stop-Process -Name llama-server -Force
```

### 约束

| 维度 | 值 |
|------|-----|
| 显存 | ~2.5GB |
| 延迟 | 单图 2-10s |
| 冲突 | 不能和 ComfyUI/SD/ACE Step 同时开 |
| 编码 | 中文输出在终端可能乱码 → 用文件保存结果再 Read |

## 引擎二：Qwen3-VL-8B（本地精读）

MiniCPM-V 粗扫后的复核引擎。强项：精确 OCR、空间关系、时间戳定位、复杂推理。GGUF Q4_K_M + mmproj F16（视觉不量化）。

### 启动

```powershell
Start-Process -NoNewWindow -FilePath "D:\tools\MiniCPM-V\llama-server.exe" `
  -ArgumentList "-m", "Qwen3VL-8B-Instruct-Q4_K_M.gguf", "--mmproj", "mmproj-Qwen3VL-8B-Instruct-F16.gguf", `
  "--port", "8765", "--host", "127.0.0.1", "-ngl", "99" `
  -WorkingDirectory "D:\tools\MiniCPM-V"
```

### 健康检查 / API 调用 / 关闭

与引擎一完全相同，端口换 **8765**。健康检查 `curl http://127.0.0.1:8765/health`；关闭 `npx kill-port 8765`。

### 约束

| 维度 | 值 |
|------|-----|
| 显存 | ~7GB |
| 延迟 | 单图 5-20s |
| 冲突 | 不能和 ComfyUI/SD/ACE Step/MiniCPM-V 同时开（16G 装不下双 VLM） |
| 编码 | 中文输出在终端可能乱码 → 用文件保存结果再 Read |

## 引擎三：GLM-4.6V（云端备选）

智谱云端视觉模型，不占显存，但有限速。

**API Base：** `https://open.bigmodel.cn/api/paas/v4`
**认证：** `Authorization: Bearer $env:ZHIPU_API_KEY`

```python
# OpenAI 兼容格式，base_url 指向智谱
from openai import OpenAI
client = OpenAI(base_url="https://open.bigmodel.cn/api/paas/v4", api_key="your-key")
response = client.chat.completions.create(
    model="glm-4.6v",
    messages=[{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
        {"type": "text", "text": "描述这张图片"}
    ]}]
)
```

**何时用 GLM：**
- 显存被 ComfyUI/SD 占满（本地双引擎都起不来）
- 不想等本地模型加载
- 需要更多视觉推理能力且 Qwen3-VL 结果仍不够

## 引擎四：Tesseract OCR（轻量文字提取）

不占显存，适合清晰印刷文字。

```powershell
python -c "
import pytesseract, sys
from PIL import Image
print(pytesseract.image_to_string(Image.open(sys.argv[1]), lang='chi_sim+eng'))
" "图片路径.png"
```

**何时用 Tesseract：** 只需提取清晰文字，不需要场景理解
**何时不用：** 手写、模糊、复杂背景 → MiniCPM-V

## 完整流程模板

```
1. 判断任务类型 → 决策树选引擎
2. 检查引擎状态 → curl health / 检查进程
3. 编码图片 → base64
4. 发送请求 → 写提示词（精确、结构化、要求中文）
5. 保存结果到文件 → 避免终端编码问题
6. Read 工具读结果
```

## 工具清单

| 工具 | 位置 | 角色 | 代价 |
|------|------|------|------|
| MiniCPM-V 4.6 | :8080 | 本地粗扫主力 | 2.5GB 显存 |
| Qwen3-VL-8B | :8765 | 本地精读复核（OCR/空间/推理） | 7GB 显存 |
| GLM-4.6V | 智谱云端 | 备选（显存满时） | API 限速 |
| Tesseract OCR | C:\Program Files\Tesseract-OCR | 文字提取 | 免费 |
