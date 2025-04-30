""" 
Resources 和 Prompts MCP Service 示例
Resources: MCP 的 markdown 文档
Prompts: prompt template
"""

from datetime import datetime
import glob
import json
import os
from typing import List
from mcp import Resource
from mcp.server.fastmcp import FastMCP
from mcp.types import Resource, TextContent, EmbeddedResource


# 初始化 FastMCP 服务器
mcp = FastMCP("SesPromptService")

# 定义文档目录常量
DOCS_DIR = "docs"
OUTPUT_DIR = "logs"

# 确保结果目录存在
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@mcp.resource("mcp-doc://4.MCP规范协议.md", description="MCP documentation: 4.MCP规范协议.md")
def get_mcp_protocol_doc() -> str:
    """获取文档内容
    
    返回：
        str: 文档内容
    """
    file_path = os.path.join(DOCS_DIR, "4.MCP规范协议.md")
    return _read_file_content(file_path)

@mcp.resource("mcp-doc://6.MCP核心交互流程.md", description="MCP documentation: 6.MCP核心交互流程.md")
def get_mcp_interaction_doc() -> str:
    """获取文档内容
    
    返回：
        str: 文档内容
    """
    file_path = os.path.join(DOCS_DIR, "6.MCP核心交互流程.md")
    return _read_file_content(file_path)

@mcp.tool(description="保存问题和回答到本地文件")
def save_to_local(file_name: str, question: str, answer: str) -> str:
    """将问题和回答保存到本地文件
    
    参数：
        file_name: 保存的文件名
        question: 用户的问题
        answer: 回答内容
    
    返回：
        str: 保存成功的消息
    """
    data = {
        "question": question,
        "answer": answer,
        "timestamp": datetime.now().isoformat()
    }
    
    file_path = os.path.join(OUTPUT_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return f"成功保存到: {file_path}"


@mcp.prompt(description="简洁回答的提示模板")
def simply_replay(question: str) -> str:
    """生成简洁回答的提示模板
    
    参数：
        question: 用户问题
    
    返回：
        str: 提示模板文本
    """
    return f"请简洁地回答以下问题:\n\n{question}"


@mcp.prompt(description="详细回答的提示模板")
def detailed_response(question: str) -> str:
    """生成详细回答的提示模板
    
    参数：
        question: 用户问题
    
    返回：
        str: 提示模板文本
    """
    return f"请详细回答以下问题:\n\n{question}"

def _read_file_content(file_path: str) -> str:
    """读取文件内容的辅助函数
    
    参数：
        file_path: 文件路径
    
    返回：
        str: 文件内容
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取文件 {file_path} 失败: {str(e)}"


if __name__ == "__main__":
    # 以标准 I/O 方式运行 MCP 服务器
    mcp.run(transport='stdio')