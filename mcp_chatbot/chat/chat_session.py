import asyncio
import json
import sys

from ..mcp.mcp_client import MCPClient
from ..llm.llm_service import LLMService

class ChatSession:
    """ 聊天会话类，协调用户、LLM和工具之间的交互
    """
    def __init__(
        self,
        clients: list[MCPClient],
        llm_service: LLMService,
    ):
        self.clients = clients
        self.llm_service = llm_service 

    async def cleanup_clients(self) -> None:
        """ 清理所有服务器
        """
        await asyncio.gather(
            *[asyncio.create_task(client.cleanup()) for client in self.clients],
            return_exceptions=True
        )

    async def process_llm_response(self, llm_response: str) -> str:
        """ 处理 LLM 的响应，并执行工具调用
        """
        try:
            llm_response = llm_response.replace("```json", "").replace("```", "")
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                # 查找对应服务器
                for server in self.clients:
                    if any(tool.name == tool_call["tool"] for tool in await server.list_tools()):
                        result = await server.execute_tool(tool_call["tool"], tool_call["arguments"])

                        # 处理进度信息
                        if isinstance(result, dict) and "progress" in result:
                            progress = (result["progress"] / result["total"]) * 100
                            print(f"[LOG]: 进度: {progress:.1f}%")
                        
                        return f"工具执行结果: {result}"
                        
                return f"未找到工具: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            print("[ERR]: LLM 响应不是有效的 JSON 格式")
            return llm_response
        
    async def start(self) -> None:
        """ 主循环聊天
        """
        try:
            # 初始化所有服务器
            for server in self.clients:
                try:
                    await server.initializer()
                except Exception as e:
                    print(f"[ERR]: 初始化 server 失败: {e}")
                    await self.cleanup_servers()
                    return

            # 收集所有工具信息
            all_tools = []
            all_tools_name = []
            for server in self.clients:
                tools = await server.list_tools()
                all_tools.extend(tools)
                all_tools_name.extend([tool.name for tool in tools])

            print(f"[SYS]: 可用工具: {all_tools_name}")

            tools_descriptions = "\n".join([tool.format_for_llm() for tool in all_tools])

            system_prompt = (
                "你是一个可以使用以下工具的有用助手:\n\n"
                f"{tools_descriptions}\n"
                "根据用户的问题选择合适的工具。 "
                "如果不需要工具，请直接回复。\n\n"
                "注意：当你需要使用工具时，必须仅以如下JSON对象格式回复，不要包含其他内容：\n "
                "{\n"
                '    "tool": "tool-name",\n'
                '    "arguments": {\n'
                '        "argument-name": "value"\n'
                "    }\n"
                "}\n\n"
                "在收到工具响应后：\n"
                "1. 将原始数据转换为自然、对话式的回复\n"
                "2. 保持回复简洁但信息丰富\n"
                "3. 专注于最相关的信息\n"
                "4. 使用用户问题中的适当上下文\n"
                "5. 避免简单重复原始数据\n\n"
                "请仅使用上述明确定义的工具。"
            )
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]

            while True:
                user_input = input("\n[USR]: ").strip().lower()
                print()
                if user_input in ["quit", "exit"]:
                    print("[SYS]: \n退出聊天")
                    break

                messages.append({"role": "user", "content": user_input})

                # 获取LLM输出
                llm_stream = self.llm_service.get_response(messages, stream=True)
                # print(f"[LOG]: {llm_response}")
                sys.stdout.write("[LOG]: ")
                sys.stdout.flush()
                llm_response = ""
                for content_chunk in llm_stream:
                    if content_chunk:
                        sys.stdout.write(content_chunk)
                        sys.stdout.flush()
                        llm_response += content_chunk
                print("\n")  # 流式输出结束后换行

                # 工具调用
                processed_result = await self.process_llm_response(llm_response)

                # 处理
                if processed_result != llm_response:
                    messages.append({"role": "assistant", "content": llm_response})
                    messages.append({"role": "system", "content": processed_result})
                    
                    llm_stream = self.llm_service.get_response(messages, stream=True)
                    # print(f"[LLM]: {final_response}")
                    sys.stdout.write("[LLM]: ")
                    sys.stdout.flush()
                    final_response = ""
                    for content_chunk in llm_stream:
                        if content_chunk:
                            sys.stdout.write(content_chunk)
                            sys.stdout.flush()
                            final_response += content_chunk
                    print("\n")  # 流式输出结束后换行

                else:
                    messages.append({"role": "assistant", "content": llm_response})
        
        finally:
            await self.cleanup_servers()