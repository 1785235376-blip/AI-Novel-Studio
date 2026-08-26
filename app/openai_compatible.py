"""Generic OpenAI-compatible text transport; contains no Novel domain logic."""
from __future__ import annotations

import json, os, time
from dataclasses import dataclass
from typing import Iterator

import httpx

from .model_runtime import (GenerationEvent, GenerationUsage, ModelRuntimeError,
                            RuntimeErrorCode, TextGenerationRequest,
                            TextGenerationResponse)


@dataclass(frozen=True, slots=True)
class CompatibleProviderConfig:
    provider_id: str
    base_url: str
    api_key_env: str
    connect_timeout: float = 10
    first_response_timeout: float = 30
    overall_timeout: float = 120


class OpenAICompatibleTextProvider:
    def __init__(self, config: CompatibleProviderConfig, *, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.provider_id = config.provider_id
        self._transport = transport

    def _key(self) -> str:
        from .credential_vault import credential_vault
        packaged = os.getenv('PACKAGED_WINDOWS_MODE','').lower() in {'1','true','yes','on'}
        try:
            from .config import settings
            packaged = packaged or settings.enable_packaged_runtime
        except Exception:
            pass
        key = credential_vault.resolve(self.provider_id)
        if not key and not packaged:
            key = os.getenv(self.config.api_key_env, "")
        if not key:
            raise ModelRuntimeError(RuntimeErrorCode.INVALID_CONFIGURATION, "模型未配置",
                                    provider_id=self.provider_id)
        return key

    def _client(self) -> httpx.Client:
        timeout = httpx.Timeout(self.config.first_response_timeout, connect=self.config.connect_timeout)
        return httpx.Client(timeout=timeout, transport=self._transport)

    def _payload(self, request: TextGenerationRequest, stream: bool) -> dict:
        messages=[]
        if request.system_instruction: messages.append({"role":"system","content":request.system_instruction})
        messages.append({"role":"user","content":request.prompt})
        body={"model":request.model_id,"messages":messages,"stream":stream}
        if stream: body["stream_options"]={"include_usage":True}
        if request.parameters.temperature is not None: body["temperature"]=request.parameters.temperature
        if request.parameters.max_output_tokens is not None: body["max_tokens"]=request.parameters.max_output_tokens
        if request.parameters.stop_sequences: body["stop"]=list(request.parameters.stop_sequences)
        return body

    def _error(self, status: int, request: TextGenerationRequest, headers: httpx.Headers) -> ModelRuntimeError:
        if status in (401,403): code,msg,retry=RuntimeErrorCode.AUTHENTICATION_FAILED,"模型凭据无效",False
        elif status == 429: code,msg,retry=RuntimeErrorCode.RATE_LIMITED,"请求过于频繁",True
        elif status == 404: code,msg,retry=RuntimeErrorCode.MODEL_NOT_FOUND,"找不到所选模型",False
        elif status in (400,422): code,msg,retry=RuntimeErrorCode.INVALID_REQUEST,"生成请求无效",False
        elif status >= 500: code,msg,retry=RuntimeErrorCode.PROVIDER_UNAVAILABLE,"模型暂时不可用",True
        else: code,msg,retry=RuntimeErrorCode.GENERATION_FAILED,"生成失败",False
        metadata={}
        retry_after=headers.get("retry-after")
        if retry_after and retry_after.isdigit(): metadata["retry_after"]=int(retry_after)
        return ModelRuntimeError(code,msg,retryable=retry,provider_id=self.provider_id,
                                 model_id=request.model_id,metadata=metadata)

    def _network_error(self, exc: Exception, request: TextGenerationRequest) -> ModelRuntimeError:
        if isinstance(exc, httpx.TimeoutException): code,msg=RuntimeErrorCode.TIMEOUT,"生成超时"
        else: code,msg=RuntimeErrorCode.PROVIDER_UNAVAILABLE,"模型暂时不可用"
        return ModelRuntimeError(code,msg,retryable=True,provider_id=self.provider_id,
                                 model_id=request.model_id) 

    @staticmethod
    def _usage(value: dict | None) -> GenerationUsage | None:
        if not value:return None
        return GenerationUsage(value.get("prompt_tokens"),value.get("completion_tokens"),value.get("total_tokens"))

    def generate_text(self, request: TextGenerationRequest) -> TextGenerationResponse:
        started=time.monotonic()
        try:
            with self._client() as client:
                response=client.post(self.config.base_url.rstrip("/")+"/chat/completions",
                    headers={"Authorization":"Bearer "+self._key()},json=self._payload(request,False))
                if response.status_code >= 400: raise self._error(response.status_code,request,response.headers)
                data=response.json(); choice=data["choices"][0]
                return TextGenerationResponse(choice["message"]["content"],choice.get("finish_reason") or "unknown",
                    self.provider_id,request.model_id,self._usage(data.get("usage")),int((time.monotonic()-started)*1000),data.get("id"))
        except ModelRuntimeError: raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc: raise self._network_error(exc,request) from exc

    def stream_text(self, request: TextGenerationRequest) -> Iterator[GenerationEvent]:
        started=time.monotonic(); chunks=[]; finish="unknown"; usage=None; reference=None
        if request.cancellation and request.cancellation.is_set():
            raise ModelRuntimeError(RuntimeErrorCode.CANCELLED,"已停止生成")
        yield GenerationEvent("generation.started",request.job_id)
        try:
            with self._client() as client:
                with client.stream("POST",self.config.base_url.rstrip("/")+"/chat/completions",
                    headers={"Authorization":"Bearer "+self._key()},json=self._payload(request,True)) as response:
                    if response.status_code >= 400: raise self._error(response.status_code,request,response.headers)
                    for line in response.iter_lines():
                        if time.monotonic()-started > self.config.overall_timeout:
                            raise ModelRuntimeError(RuntimeErrorCode.TIMEOUT,"生成超时",retryable=True,
                                provider_id=self.provider_id,model_id=request.model_id,metadata={"phase":"OVERALL"})
                        if request.cancellation and request.cancellation.is_set():
                            raise ModelRuntimeError(RuntimeErrorCode.CANCELLED,"已停止生成")
                        if not line.startswith("data:"): continue
                        payload=line[5:].strip()
                        if payload == "[DONE]": break
                        item=json.loads(payload); reference=reference or item.get("id"); usage=self._usage(item.get("usage")) or usage
                        for choice in item.get("choices",[]):
                            delta=(choice.get("delta") or {}).get("content") or ""
                            if delta: chunks.append(delta); yield GenerationEvent("generation.delta",request.job_id,delta=delta)
                            if choice.get("finish_reason"): finish=choice["finish_reason"]
            text="".join(chunks)
            result=TextGenerationResponse(text,finish,self.provider_id,request.model_id,usage,
                int((time.monotonic()-started)*1000),reference)
            yield GenerationEvent("generation.completed",request.job_id,response=result)
        except ModelRuntimeError: raise
        except (httpx.HTTPError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise self._network_error(exc,request) from exc
