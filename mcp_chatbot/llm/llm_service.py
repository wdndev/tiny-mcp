from openai import OpenAI
from typing import Generator, Optional, Union
import warnings

class LLMService:
    """同步方式LLM服务类"""
    
    def __init__(
        self, 
        api_key: str,
        model_name: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        model_type: str = "deepseek"
    ):
        """
        初始化LLM服务
        
        :param api_key: API密钥（必须）
        :param model_name: 模型名称，默认deepseek-chat
        :param base_url: API基础URL，默认deepseek
        :param model_type: 服务类型，支持openai/deepseek
        """
        if not api_key:
            raise ValueError("API key is required")

        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url

        # 初始化同步客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=None if model_type == "openai" else base_url
        )

    def get_response(
        self, 
        messages: list[dict[str, str]],
        stream: bool = False
    ) -> Union[str, Generator[str, None, None]]:
        """
        获取同步LLM响应
        
        :param messages: OpenAI格式消息历史
        :param stream: 是否启用流式模式
        :return: 字符串或生成器
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=4096,
                stream=stream
            )

            if stream:
                return self._handle_stream_response(response)
            return response.choices[0].message.content
            
        except Exception as e:
            error_msg = f"LLM请求失败: {str(e)}"
            if stream:
                def error_generator():
                    yield error_msg
                return error_generator()
            return error_msg

    def _handle_stream_response(
        self, 
        response: Generator
    ) -> Generator[str, None, None]:
        """处理流式响应"""
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

if __name__ == "__main__":
    llm = LLMService(api_key="sk-f294ffdaf91f41108e550562911e013c")
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "你好"},
    ]

    res = llm.get_response(messages, stream=True)

    # print(res)
    for content_chunk in res:
        print(content_chunk, end="", flush=True)
