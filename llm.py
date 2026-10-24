"""大模型调用：OpenAI 兼容接口。未配置时返回 None 以触发本地模拟。"""
from openai import OpenAI

PROVIDERS = {
    "OpenAI": {"api_base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "DeepSeek": {"api_base": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "通义千问": {"api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "智谱GLM": {"api_base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "月之暗面Kimi": {"api_base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "自定义": {"api_base": "", "model": ""},
}


def is_configured(config: dict | None) -> bool:
    return bool(
        config
        and config.get("api_key")
        and config.get("api_base")
        and config.get("model")
    )


def chat(config: dict | None, system: str, user: str, temperature: float = 0.7) -> str | None:
    """调用大模型；未配置返回 None，调用失败返回以 [调用失败] 开头的错误串。"""
    if not is_configured(config):
        return None
    try:
        client = OpenAI(
            base_url=config["api_base"],
            api_key=config["api_key"],
            timeout=60,
        )
        resp = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[调用失败] {e}"