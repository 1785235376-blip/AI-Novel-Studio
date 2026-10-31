# 本地 VIDEO 时间线渲染（2026-10-31）

## 能力
`tests/test_studio_video_timeline_local_render.py` 验证现有 Studio 时间线渲染链可把**正式 video Asset** 作为 VIDEO 轨来源，在本机 FFmpeg 下渲染为 `REVIEW_MP4` 候选：

- 合成源：本机 FFmpeg 生成 320x180 1s MP4（红色画面 + AAC 440Hz 音频），作为正式 video Asset（File owner）；
- 时间线 schema 2：VIDEO 轨 clip pin source id/version/digest、in/out、include_audio；
- 原链：`timeline_save` → `timeline_export_preview` → `timeline_export` → candidate → review；
- FFprobe：`mpeg4` 320x180、AAC 48kHz stereo、约 1s；候选 sha256 与正式资产字节一致；
- 人工 review 后 APPROVED，正式资产可回读。

本机真实 FFmpeg/FFprobe；1 passed。

## 边界
真实模型视频生成、真实 NLE、其他编解码/多轨复杂组合、PG/浏览器/打包桌面仍 NOT_RUN；不得将本测试当作真实视频模型验收。
