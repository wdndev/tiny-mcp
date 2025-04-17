import asyncio
import os
import sys
import json
from contextlib import AsyncExitStack
from typing import Optional, List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(
        self,
        model_type: str,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model_name: str = "deepseek-chat",
    ):
        """
        初始化MCP客户端
        :param model_type: 服务商类型 ("openai"/"deepseek")
        :param api_key: API密钥
        :param base_url: API端点
        :param model_name: 模型名称
        """
        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url

        # 初始化会话参数
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.available_tools: List[Dict[str, Any]] = []

        # 初始化客户端
        if model_type == "openai":
            self.client = AsyncOpenAI(api_key=api_key)
        elif model_type == "deepseek":
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        else:
            raise ValueError(f"[ERR]: 不支持的模型类型: {model_type}")
    async def connect_to_server(self, server_script_path: str):
        """
        连接到MCP服务器
        :param server_script_path: 服务器脚本路径（.py或.js）
        """
        # 验证文件类型
        if not server_script_path.endswith(('.py', '.js')):
            raise ValueError("[ERR]: 服务器脚本必须是.py或.js文件")

        # 构建执行命令
        command = "python" if server_script_path.endswith('.py') else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        # 建立传输层连接
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio_reader, stdio_writer = stdio_transport

        # 初始化客户端会话
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_reader, stdio_writer)
        )
        await self.session.initialize()

        # 获取可用工具列表
        response = await self.session.list_tools()
        self.available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            for tool in response.tools
        ]
        print(f"[SYS]: 成功连接服务器，可用工具: {[t['function']['name'] for t in self.available_tools]}")

    async def process_query(self, query: str) -> str:
        """处理查询
        """
        messages = [{"role": "user", "content": query}]
        responses = []

        while True:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.available_tools,
                    tool_choice="auto",
                )

                message = response.choices[0].message
                messages.append(message)

                if not message.tool_calls:
                    return message.content or ""

                # 处理工具调用
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    
                    # 增强参数解析
                    if isinstance(tool_call.function.arguments, dict):
                        tool_args = tool_call.function.arguments
                    else:
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {"input": tool_call.function.arguments}

                    # 执行工具调用
                    result = await self.session.call_tool(tool_name, tool_args)
                    print(f"[LOG]: 调用工具 [{tool_name}] 参数: {tool_args}")
                    responses.append(f"[调用工具] {tool_name} 参数: {tool_args}")

                    # 通用工具响应格式
                    tool_response = {
                        "role": "tool",
                        "content": str(result.content),
                        "tool_call_id": tool_call.id,
                        "name": tool_name  # 所有服务商统一添加name字段
                    }
                    messages.append(tool_response)

            except Exception as e:
                responses.append(f"[ERR]: 处理错误: {str(e)}")
                break

        return "\n".join(responses)

    async def chat_loop(self):
        """改进的输入处理方法"""
        print("[SYS]: MCP客户端已启动！")
        print("[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）")

        loop = asyncio.get_event_loop()
        
        while True:
            try:
                # 使用run_in_executor处理同步输入
                query = await loop.run_in_executor(
                    None,  # 使用默认执行器
                    lambda: input("[USR]: ").strip()
                )
                
                if not query:
                    continue
                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print(f"\n[LLM]: {response} \n")

            except (KeyboardInterrupt, EOFError):
                print("\n[SYS]: 检测到退出信号，正在关闭...")
                break
            except Exception as e:
                print(f"\n[SYS]: 错误发生：{str(e)}")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()

async def main():

    if len(sys.argv) < 2:
        print("使用方法: python client.py <服务器脚本路径>")
        sys.exit(1)

    client = MCPClient(
        model_type=os.getenv("LLM_MODEL_TYPE", ""),
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_API_URL", ""),
        model_name=os.getenv("LLM_MODEL_NAME", ""),
    )

    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())