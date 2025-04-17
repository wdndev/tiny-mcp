


调试：

```bash
(tiny-mcp) PS tiny-mcp> mcp dev E:/04Code/llm/mcp_code/tiny-mcp-demo/services/weather_service_zh.py
Starting MCP inspector...
🔍 MCP Inspector is up and running at http://127.0.0.1:6274 🚀
⚙️ Proxy server listening on port 6277
```


```bash
(tiny-mcp) PS tiny-mcp> python mcp_client.py E:/04Code/llm/mcp_code/tiny-mcp-demo/services/weather_service_zh.py
[SYS]: 成功连接服务器，可用工具: ['get_weather']
[SYS]: MCP客户端已启动！
[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）
[USR]: 北京天气如何？适合去天安门吗？
[LOG]: 调用工具 [get_weather] 参数: {'location': '北京'}

[LLM]: 北京的天气是多云，温度为29°C，体感温度26°C，北风3级，湿度较低（18%），能见度良好（21公里）。

这样的天气适合去天安门游玩，但建议注意防晒和补水，因为湿度较低可能会感觉干燥。 

[USR]: 现在沈阳的天气怎么样呢？能出去踢足球吗？
[LOG]: 调用工具 [get_weather] 参数: {'location': '沈阳'}

[LLM]: 沈阳目前有小雨，气温为15°C，体感温度14°C，西南风2级，风速8公里/小时，相对湿度74%。由于有小雨，场地可能会比较湿滑，不太适合踢足球。建议等天气转晴后再安排户外活动。 

[USR]: quit
```


