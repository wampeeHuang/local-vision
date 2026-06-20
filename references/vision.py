"""
本地视觉增强 — 可复用的视觉调用脚本
三引擎：MiniCPM-V (本地)、GLM-4.6V (云端)、Tesseract (OCR)

Usage:
    python vision.py minicpm image.jpg "描述这张图片"
    python vision.py glm image.jpg "这张图里有什么？"
    python vision.py ocr image.png
"""

import urllib.request, json, base64, sys, os


def minicpm_vision(image_path, prompt="描述这张图片的内容。用中文回答。"):
    """本地 MiniCPM-V 4.6，需先启动 llama-server :8080"""
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()

    ext = os.path.splitext(image_path)[1].lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext.lstrip('.'), 'jpeg')

    body = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }],
        "max_tokens": 600
    }
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    content = result["choices"][0]["message"]["content"]
    reasoning = result["choices"][0]["message"].get("reasoning_content", "")
    if reasoning:
        print(f"[reasoning]\n{reasoning}\n[/reasoning]\n")
    print(content)
    return content


def glm_vision(image_path, prompt="描述这张图片的内容。用中文回答。"):
    """云端 GLM-4.6V，需要 ZHIPU_API_KEY 环境变量"""
    api_key = os.environ.get("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("ZHIPU_API_KEY 环境变量未设置")

    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()

    ext = os.path.splitext(image_path)[1].lower()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext.lstrip('.'), 'jpeg')

    body = {
        "model": "glm-4.6v",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/{mime};base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }],
        "max_tokens": 600
    }
    req = urllib.request.Request("https://open.bigmodel.cn/api/paas/v4/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    print(result["choices"][0]["message"]["content"])


def tesseract_ocr(image_path, lang='chi_sim+eng'):
    """Tesseract OCR 文字提取"""
    import pytesseract
    from PIL import Image
    text = pytesseract.image_to_string(Image.open(image_path), lang=lang)
    print(text)
    return text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vision.py <engine> <image> [prompt]")
        print("  engine: minicpm | glm | ocr")
        sys.exit(1)

    engine = sys.argv[1]
    image = sys.argv[2]
    prompt = sys.argv[3] if len(sys.argv) > 3 else "描述这张图片的内容。用中文回答。"

    engines = {"minicpm": minicpm_vision, "glm": glm_vision, "ocr": tesseract_ocr}
    if engine not in engines:
        print(f"未知引擎: {engine}，可选: {list(engines.keys())}")
        sys.exit(1)

    engines[engine](image, prompt)
