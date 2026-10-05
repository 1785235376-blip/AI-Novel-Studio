"""Opt-in native text protocols; never execute tools or retry a billed request.

Sources and verification limits: docs/delivery/dot-astra-rc-r2/runtime-work.md.
Model IDs must be provided by the host; no vendor model is guessed here.
"""
from __future__ import annotations

import json
import time
from urllib.parse import quote

import httpx

from .openai_compatible import OpenAICompatibleTextProvider
from .model_runtime import (GenerationEvent, GenerationUsage, ModelRuntimeError,
                            RuntimeErrorCode, TextGenerationResponse)


class NativeTextProvider(OpenAICompatibleTextProvider):
    protocol: str

    def _check(self, request, started):
        if request.cancellation and request.cancellation.is_set():
            raise ModelRuntimeError(RuntimeErrorCode.CANCELLED,"已停止生成")
        if time.monotonic()-started > self.config.overall_timeout:
            raise ModelRuntimeError(RuntimeErrorCode.TIMEOUT,"生成超时",metadata={"replay_safe":False})

    def _request(self, request, stream):
        key=self._key()
        if self.protocol=="anthropic":
            body={"model":request.model_id,"messages":[{"role":"user","content":request.prompt}],
                  "max_tokens":request.parameters.max_output_tokens or 1024,"stream":stream}
            if request.system_instruction:body["system"]=request.system_instruction
            if request.parameters.temperature is not None:body["temperature"]=request.parameters.temperature
            if request.parameters.stop_sequences:body["stop_sequences"]=list(request.parameters.stop_sequences)
            return self.config.base_url.rstrip("/")+"/messages", {"x-api-key":key,"anthropic-version":"2023-06-01"}, body
        model=request.model_id.removeprefix("models/")
        method="streamGenerateContent?alt=sse" if stream else "generateContent"
        body={"contents":[{"role":"user","parts":[{"text":request.prompt}]}],"generationConfig":{}}
        if request.system_instruction:body["systemInstruction"]={"parts":[{"text":request.system_instruction}]}
        if request.parameters.temperature is not None:body["generationConfig"]["temperature"]=request.parameters.temperature
        if request.parameters.max_output_tokens:body["generationConfig"]["maxOutputTokens"]=request.parameters.max_output_tokens
        if request.parameters.stop_sequences:body["generationConfig"]["stopSequences"]=list(request.parameters.stop_sequences)
        return self.config.base_url.rstrip("/")+"/models/"+quote(model,safe="")+":"+method, {"x-goog-api-key":key}, body

    def _decode(self, data):
        if not isinstance(data,dict):raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED,"模型响应格式无效")
        if self.protocol=="anthropic":
            if any(block.get("type") in {"tool_use","server_tool_use"} for block in data.get("content",[])):
                raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED,"此文本适配器不执行工具调用")
            text="".join(block.get("text","") for block in data.get("content",[]) if block.get("type")=="text")
            value=data.get("usage")
            usage=GenerationUsage(value.get("input_tokens"),value.get("output_tokens")) if value else None
            return text,data.get("stop_reason") or "unknown",usage,data.get("id")
        if data.get("promptFeedback",{}).get("blockReason"):
            raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED,"模型未返回可用文本")
        candidates=data.get("candidates") or []
        if not candidates:return "","unknown",None,None
        choice=candidates[0]
        if choice.get("finishReason") in {"SAFETY","RECITATION","BLOCKLIST","PROHIBITED_CONTENT","SPII","MALFORMED_FUNCTION_CALL"}:
            raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED,"模型未返回可用文本")
        parts=choice.get("content",{}).get("parts",[])
        if any("functionCall" in part for part in parts):
            raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED,"此文本适配器不执行工具调用")
        text="".join(part.get("text","") for part in parts if not part.get("thought"))
        value=data.get("usageMetadata")
        usage=GenerationUsage(value.get("promptTokenCount"),value.get("candidatesTokenCount"),value.get("totalTokenCount")) if value else None
        return text,choice.get("finishReason") or "unknown",usage,data.get("responseId")

    def generate_text(self, request):
        started=time.monotonic();self._check(request,started)
        url,headers,body=self._request(request,False)
        try:
            with self._client() as client:
                response=client.post(url,headers=headers,json=body)
                self._check(request,started)
                if response.status_code>=400:raise self._error(response.status_code,request,response.headers)
                text,finish,usage,reference=self._decode(response.json())
                if not text or finish=="unknown":raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED,"模型响应未完成")
                return TextGenerationResponse(text,finish,self.provider_id,request.model_id,usage,int((time.monotonic()-started)*1000),reference)
        except ModelRuntimeError:raise
        except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as exc:
            raise self._network_error(exc,request) from exc

    def stream_text(self, request):
        started=time.monotonic();self._check(request,started)
        url,headers,body=self._request(request,True)
        chunks=[];finish="unknown";usage=None;reference=None;done=False;counts={}
        yield GenerationEvent("generation.started",request.job_id)
        try:
            with self._client() as client:
                with client.stream("POST",url,headers=headers,json=body) as response:
                    if response.status_code>=400:raise self._error(response.status_code,request,response.headers)
                    for line in response.iter_lines():
                        self._check(request,started)
                        if not line.startswith("data:"):continue
                        data=json.loads(line[5:].strip())
                        if not isinstance(data,dict):raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED,"模型响应格式无效")
                        if "error" in data:raise ModelRuntimeError(RuntimeErrorCode.PROVIDER_UNAVAILABLE,"模型流式请求失败",metadata={"replay_safe":False})
                        delta=""
                        if self.protocol=="anthropic":
                            kind=data.get("type")
                            if kind=="message_start":
                                message=data.get("message",{});reference=message.get("id");counts.update(message.get("usage",{}))
                            elif kind=="content_block_start" and data.get("content_block",{}).get("type") in {"tool_use","server_tool_use"}:
                                raise ModelRuntimeError(RuntimeErrorCode.CAPABILITY_NOT_SUPPORTED,"此文本适配器不执行工具调用")
                            elif kind=="content_block_start" and data.get("content_block",{}).get("type")=="text":delta=data["content_block"].get("text","")
                            elif kind=="content_block_delta" and data.get("delta",{}).get("type")=="text_delta":delta=data["delta"].get("text","")
                            elif kind=="message_delta":
                                counts.update(data.get("usage",{}));finish=data.get("delta",{}).get("stop_reason") or finish
                            elif kind=="message_stop":done=True
                            if counts:usage=GenerationUsage(counts.get("input_tokens"),counts.get("output_tokens"))
                        else:
                            delta,new_finish,new_usage,new_reference=self._decode(data)
                            finish=new_finish if new_finish!="unknown" else finish
                            usage=new_usage or usage;reference=new_reference or reference
                            done=finish!="unknown"
                        if delta:chunks.append(delta);yield GenerationEvent("generation.delta",request.job_id,delta=delta)
                        if self.protocol=="anthropic" and done:break
            self._check(request,started)
            if not done or not chunks:raise ModelRuntimeError(RuntimeErrorCode.GENERATION_FAILED,"模型连接中断，结果未完成",metadata={"replay_safe":False})
            yield GenerationEvent("generation.completed",request.job_id,response=TextGenerationResponse("".join(chunks),finish,self.provider_id,request.model_id,usage,int((time.monotonic()-started)*1000),reference))
        except ModelRuntimeError:raise
        except (httpx.HTTPError,ValueError,KeyError,IndexError,TypeError) as exc:
            raise self._network_error(exc,request) from exc


class AnthropicTextProvider(NativeTextProvider):
    protocol="anthropic"


class GeminiTextProvider(NativeTextProvider):
    protocol="gemini"
