# Timeline 音频导出：PCM16 / PCM24（2026-10-31）

## 能力
`app/services/studio_timeline_export.py` 的封闭导出预设新增 `AUDIO_WAV_PCM24`：
- 48 kHz、双声道、24-bit PCM（`pcm_s24le`），bitexact WAV；
- 精确字节预算：classic PCM16 头 44 字节；extensible PCM24 头 68 字节；
- 输出证明用 `media_files.inspect_wav_metadata` 校验 RIFF/`fmt `/`data` 边界、format tag（1 或 0xFFFE+PCM sub-format）、通道/采样率/位宽/帧数与 ffprobe 编码；
- `AUDIO_WAV_PCM16` 行为不变；时间线渲染、混音、审批、正式资产回读路径共用。

## 测试
`tests/test_studio_timeline_audio_profiles.py`：
- PCM16/PCM24 参数化多轨（440 Hz + 880 Hz muted）真实 FFmpeg/FFprobe；
- 校验编码/采样率/位宽/精确文件字节数/审批/正式资产字节。
2 passed；相关 media/timeline/video 组 11 passed/1 skipped（1 error 为既有旧 fixture 错误）。

## 边界
仅 File/Windows 合成与真实本机 FFmpeg；真实 NLE/外部平台、其他编解码/多轨恢复仍 NOT_RUN。
