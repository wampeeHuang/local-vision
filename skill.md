---
name: local-vision
description: 本地视觉增强。三引擎视觉理解（MiniCPM-V本地/GLM-4.6V云端/Tesseract OCR），为纯文本模型提供外置眼睛。适用：读图、OCR、截图理解、产品图分析。
---

# 本地视觉增强

DeepSeek v4 Pro API 不能直接看图片。本 skill 用外部视觉模型做外置眼睛。

## 决策树

```
需要做什么？
├── 提取图片中的文字（清晰印刷体）→ Tesseract OCR（<1s，不占显存）
├── 理解图片内容/场景/产品 → MiniCPM-V（首选，免费本地 2-10s）
└── MiniCPM-V 未启动且不想等 → GLM-4.6V（云端，3-10s，限速）
```

**NOT for：** 生成图片 → ComfyUI / aigoapi gpt-image-2

## 引擎一：MiniCPM-V 4.6（本地主力）

OpenAI 兼容 API，推理速度 ~290 t/s GPU。

### 启动

```powershell
Start-Process -NoNewWindow -FilePath "$env:USERPROFILE\llama-cpp\llama-server.exe" `
  -ArgumentList "-m", "MiniCPM-V-4_6-Q4_K_M.gguf", "--mmproj", "mmproj-MiniCPM-V-4_6-f16.gguf", `
  "--port", "8080", "--host", "127.0.0.1", "-ngl", "99" `
  -WorkingDirectory "$env:USERPROFILE\llama-cpp"
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

## 引擎二：GLM-4.6V（云端备选）

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
- MiniCPM-V 未启动且不想等
- 显存紧张（ComfyUI/SD 在跑）
- 需要更多视觉推理能力

## 引擎三：Tesseract OCR（轻量文字提取）

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
| MiniCPM-V 4.6 | :8080 | 本地主力 | 2.5GB 显存 |
| GLM-4.6V | 智谱云端 | 备选 | API 限速 |
| Tesseract OCR | C:\Program Files\Tesseract-OCR | 文字提取 | 免费 |
