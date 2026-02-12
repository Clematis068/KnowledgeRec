from openai import OpenAI
from ..config import Config


class QwenService:
    """通义千问 API 封装，使用 OpenAI 兼容接口"""

    def __init__(self):
        self.client = OpenAI(
            api_key=Config.DASHSCOPE_API_KEY,
            base_url=Config.DASHSCOPE_BASE_URL,
        )
        self.model = Config.QWEN_MODEL

    def chat(self, message: str, system_prompt: str = None) -> str:
        """单轮对话"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": message})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content

    def chat_with_history(self, messages: list[dict]) -> str:
        """多轮对话，messages 格式: [{"role": "user/assistant/system", "content": "..."}]"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content

    def get_embedding(self, text: str) -> list[float]:
        """获取文本向量，用于语义相似度计算"""
        response = self.client.embeddings.create(
            model="text-embedding-v3",
            input=text,
        )
        return response.data[0].embedding

    def extract_tags(self, content: str) -> dict:
        """从内容中提取标签和摘要，用于知识图谱构建"""
        system_prompt = (
            "你是知识社区内容分析助手。请从以下内容中提取：\n"
            "1. tags: 3-5个核心标签\n"
            "2. summary: 一句话摘要\n"
            "3. domain: 所属知识领域\n"
            "请严格以JSON格式返回，不要输出其他内容。"
        )
        import json
        result = self.chat(content, system_prompt=system_prompt)
        return json.loads(result)


# 全局单例
qwen_service = QwenService()
