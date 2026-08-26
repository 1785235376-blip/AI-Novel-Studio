# Model Runtime

LOCAL_ONLY 路由至 Ollama；开发时 `MOCK_PROVIDER=true` 路由至 Mock。HYBRID/QUALITY 优先相应 Cloud Provider，失败后进入 Local/Mock。Anthropic/Gemini 配置状态可见，但原生 Adapter 仍未实现。API 响应不包含 Key。
