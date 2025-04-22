import asyncio
import re
import os
import sys
import json
from contextlib import AsyncExitStack
from typing import Optional, List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from dotenv import load_dotenv, dotenv_values

load_dotenv(
    dotenv_path=".env", 
    override=True
)

class MCPClient:
    def __init__(
        self,
        model_type: str,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model_name: str = "deepseek-chat",
    ):
        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url

        self.session: Optional[ClientSession] = None
        self.stdio_transport = None
        self.exit_stack = AsyncExitStack()
        self.available_tools: List[Dict[str, Any]] = []
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()

        self.llm_client = AsyncOpenAI(
            api_key=api_key,
            base_url=None if model_type == "openai" else base_url,
        )
        
    @staticmethod
    def parse_arguments(args: List[str]) -> StdioServerParameters:
        if len(args) == 1:
            server_script_path = args[0]
            if not server_script_path.endswith(('.py', '.js')):
                raise ValueError("[ERR] 服务器脚本必须是 .py 或 .js 文件")
            
            command = "python" if server_script_path.endswith('.py') else "node"
            return StdioServerParameters(
                command=command,
                args=[server_script_path],
                env=None
            )
        elif len(args) == 2:
            server_identifier, config_path = args[0], args[1]
            
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                raise ValueError(f"配置文件读取失败: {str(e)}")
            
            mcp_servers = config.get('mcpServers', {})
            server_config = mcp_servers.get(server_identifier)
            if not server_config:
                raise ValueError(f"未找到服务器标识符: {server_identifier}")
            
            if not all(key in server_config for key in ['command', 'args']):
                raise ValueError("服务器配置缺少必要字段（command/args）")
            
            return StdioServerParameters(
                command=server_config['command'],
                args=server_config['args'],
                env=None
            )
        else:
            raise ValueError("参数数量错误")

    async def connect_to_server(self, server_params: StdioServerParameters):
        self.stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio_reader, stdio_writer = self.stdio_transport

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_reader, stdio_writer)
        )
        await self.session.initialize()

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

    async def process_query(self, query: str, messages: List[dict] = None, depth: int = 0) -> str:
        if depth >= 5:
            return "[ERR] 超过最大递归深度，请检查工具调用逻辑"

        messages = messages.copy() if messages else [{"role": "user", "content": query}]
        full_response = ""
        tool_calls_cache = {}

        print("[LOG] Call LLM Messages:", messages)
        print("[LOG] Call LLM Tools:", self.available_tools)

        # 发起流式请求
        stream = await self.llm_client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=self.available_tools,
            tool_choice="auto",
            stream=True,
        )

        sys.stdout.write("[LLM]: ")
        sys.stdout.flush()

        async for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # 处理自然语言回答内容
            if delta.content:
                sys.stdout.write(delta.content)
                sys.stdout.flush()
                full_response += delta.content

            # 处理工具调用增量参数
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    index = tool_call.index
                    if index not in tool_calls_cache:
                        tool_calls_cache[index] = {
                            "id": "", 
                            "name": "", 
                            "arguments": ""
                        }
                    cached = tool_calls_cache[index]
                    cached["id"] = tool_call.id or cached["id"]
                    cached["name"] = tool_call.function.name or cached["name"]
                    cached["arguments"] += tool_call.function.arguments or ""

        print("\n")  # 流式输出结束后换行

        # 处理工具调用逻辑
        if tool_calls_cache:
            # 构造完整的工具调用参数日志
            tool_calls_log = [
                {
                    "name": call["name"],
                    "arguments": json.loads(call["arguments"]) if call["arguments"] else {}
                } 
                for call in tool_calls_cache.values()
            ]
            print(f"[LOG]: 完整工具调用参数: {json.dumps(tool_calls_log, ensure_ascii=False)}")

            # 将工具调用信息添加到messages
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "id": call["id"],
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"]
                        }
                    }
                    for call in tool_calls_cache.values()
                ]
            })

            # 执行工具调用并递归处理
            for tool_call in tool_calls_cache.values():
                tool_name = tool_call["name"]
                try:
                    tool_args = json.loads(tool_call["arguments"])
                except json.JSONDecodeError:
                    tool_args = {"input": tool_call["arguments"]}

                result = await self.session.call_tool(tool_name, tool_args)
                print(f"[LOG]: 调用结果: {result.model_dump()}")
                print(f"[LOG]: 调用工具 [{tool_name}] 参数: {tool_args}")
                print(f"[LOG]: 工具响应: {result.content}\n")

                messages.append({
                    "role": "tool",
                    # "content": getattr(result.content, 'text', str(result.content)),
                    "content": result.model_dump()["content"],
                    "tool_call_id": tool_call["id"],
                    "name": tool_name
                })

                return await self.process_query(query, messages, depth + 1)

        return full_response

    async def chat_loop(self):
        print("[SYS]: MCP客户端已启动！")
        print("[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）")

        loop = asyncio.get_event_loop()
        
        while True:
            try:
                query = await loop.run_in_executor(
                    None,
                    lambda: input("[USR]: ").strip()
                )

                print()
                
                if not query:
                    continue
                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                # process_query 中流式打印了，这儿可以不用打印
                # print(f"[LLM]: {response}")

            except (KeyboardInterrupt, EOFError):
                print("\n[SYS]: 检测到退出信号，正在关闭...")
                break
            except Exception as e:
                print(f"\n[SYS]: 错误发生：{str(e)}")

    async def cleanup(self):
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                print(f"Error during cleanup of server: {e}")

async def main():
    try:
        server_params = MCPClient.parse_arguments(sys.argv[1:])
    except ValueError as e:
        print(f"[ERR]: 参数错误: {str(e)}")
        print("使用方法:")
        print("方式 1: python mcp_client.py <服务器脚本路径>")
        print("方式 2: python mcp_client.py <服务器标识符> <配置文件路径>")
        sys.exit(1)

    model_type = os.getenv("LLM_MODEL_TYPE", "")
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_API_URL", "")
    model_name = os.getenv("LLM_MODEL_NAME", "")

    print("[SYS]: LLM_MODEL_TYPE: ", model_type)
    print("[SYS]:    LLM_API_URL: ", base_url)
    print("[SYS]: LLM_MODEL_NAME: ", model_name)
    client = MCPClient(
        model_type=model_type,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
    )

    try:
        await client.connect_to_server(server_params)
        await client.chat_loop()
    except ValueError as e:
        print(f"[ERR] 参数错误: {str(e)}")
    except Exception as e:
        print(f"\n[ERR] 运行时错误: {str(e)}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
