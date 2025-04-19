import asyncio
import json

from loguru import logger

from .mcp_server import MCPServer
from .llm_service import LLMService

class ChatSession:
    """ 聊天会话类，协调用户、LLM和工具之间的交互
    """
    def __init__(
        self,
        servers: list[MCPServer],
        llm_service: LLMService,
    ):
        self.servers = servers
        self.llm_service = llm_service 

    async def cleanup_servers(self) -> None:
        """ 清理所有服务器
        """
        await asyncio.gather(
            *[asyncio.create_task(server.cleanup()) for server in self.servers],
            return_exceptions=True
        )

    async def process_llm_response(self, llm_response: str) -> str:
        """ 处理 LLM 的响应，并执行工具调用
        """
        try:
            llm_response = llm_response.replace("```json", "").replace("```", "")
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                logger.info(f"执行工具: {tool_call['tool']}")
                logger.info(f"工具参数: {tool_call['arguments']}")
                # 查找对应服务器
                for server in self.servers:
                    if any(tool.name == tool_call["tool"] for tool in await server.list_tools()):
                        result = await server.execute_tool(tool_call["tool"], tool_call["arguments"])

                        # 处理进度信息
                        if isinstance(result, dict) and "progress" in result:
                            progress = (result["progress"] / result["total"]) * 100
                            logger.info(f"进度: {progress:.1f}%")
                        
                        return f"工具执行结果: {result}"
                        
                return f"未找到工具: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            logger.warning("LLM 响应不是有效的 JSON 格式")
            return llm_response
        
    async def start(self) -> None:
        """ 主循环聊天
        """
        try:
            # 初始化所有服务器
            for server in self.servers:
                try:
                    await server.initializer()
                except Exception as e:
                    logger.error(f"初始化 server 失败: {e}")
                    await self.cleanup_servers()
                    return

            # 收集所有工具信息
            all_tools = []
            for server in self.servers:
                tools = await server.list_tools()
                all_tools.extend(tools)

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
                user_input = input("[User]: ").strip().lower()
                if user_input in ["quit", "exit"]:
                    logger.info("\n退出聊天")
                    break

                messages.append({"role": "user", "content": user_input})

                # 获取LLM输出
                llm_response = self.llm_service.get_response(messages)
                logger.info(f"\nAssistant: {llm_response}")

                # 工具调用
                processed_result = await self.process_llm_response(llm_response)

                print("processed_result: ", processed_result)

                # 处理
                if processed_result != llm_response:
                    messages.append({"role": "assistant", "content": llm_response})
                    messages.append({"role": "system", "content": processed_result})
                    
                    final_response = self.llm_service.get_response(messages)
                    logger.info(f"\n最终响应: {final_response}")
                else:
                    messages.append({"role": "assistant", "content": llm_response})
        
        finally:
            await self.cleanup_servers()