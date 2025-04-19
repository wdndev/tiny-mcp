from loguru import logger
from openai import AsyncOpenAI, OpenAI

class LLMService:
    def __init__(
        self, 
        api_key: str, 
        model_name: str = "deepseek-chat", 
        base_url: str = "https://api.deepseek.com",
        model_type: str = "deepseek"
    ):
        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url

        self.llm_client = OpenAI(
            api_key=api_key,
            base_url=None if model_type == "openai" else base_url,
        )

    def get_response(self, messages: list[dict[str, str]]) -> str:
        """
        获取LLM响应
        
        参数:
            messages: 消息历史（OpenAI格式）
        """
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=4096,
                stream=False,
                stop=None
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM请求失败: {str(e)}")
            return f"遇到错误: {str(e)}，请重试或重新表述请求"
        

if __name__ == "__main__":
    llm = LLMService(api_key="sk-xxxxxxxxxx")
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "你好"},
    ]

    res = llm.get_response(messages)

    print(res)