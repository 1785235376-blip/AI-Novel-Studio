"""Finite, observed ComfyUI video recipes. Metadata never proves inference.

The node contracts follow the official ComfyUI LTX-Video 0.9.5, Hunyuan 1.0
and Wan 2.2 TI2V-5B examples. No user-supplied workflow, installer or downloader
is accepted. Other model versions must acquire their own validated recipe.
"""
from __future__ import annotations

import copy
from .studio_image_provider_recipes import _component, _options, validate_workflow

RECIPES = (
    {"id": "comfy-ltx095-video-v1", "display_name": "LTX-Video 0.9.5 fixed video recipe",
     "family": "LTX", "capability": "VIDEO", "model_loader": "CheckpointLoaderSimple",
     "model_input": "ckpt_name", "required_nodes": ["CheckpointLoaderSimple", "CLIPLoader", "CLIPTextEncode",
        "EmptyLTXVLatentVideo", "LTXVConditioning", "LTXVScheduler", "KSamplerSelect", "SamplerCustom", "VAEDecode", "SaveWEBM"]},
    {"id": "comfy-wan22-ti2v5b-v1", "display_name": "Wan 2.2 TI2V-5B fixed video recipe",
     "family": "WAN", "capability": "VIDEO", "model_loader": "UNETLoader", "model_input": "unet_name",
     "required_nodes": ["UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode", "ModelSamplingSD3",
        "Wan22ImageToVideoLatent", "KSampler", "VAEDecode", "SaveWEBM"]},
    {"id": "comfy-hunyuan10-t2v-v1", "display_name": "Hunyuan Video 1.0 T2V fixed video recipe",
     "family": "HUNYUAN_VIDEO", "capability": "VIDEO", "model_loader": "UNETLoader", "model_input": "unet_name",
     "required_nodes": ["UNETLoader", "DualCLIPLoader", "VAELoader", "CLIPTextEncode", "ModelSamplingSD3",
        "EmptyHunyuanLatentVideo", "FluxGuidance", "RandomNoise", "BasicGuider", "KSamplerSelect",
        "BasicScheduler", "SamplerCustomAdvanced", "VAEDecode", "SaveWEBM"]},
)
PARAMETERS = ("width", "height", "seed", "negative_prompt", "duration_seconds", "frame_rate")


def timing(recipe, parameters):
    if set(parameters) - set(PARAMETERS):
        raise ValueError("STUDIO_VIDEO_RECIPE_PARAMETER_UNSUPPORTED")
    width, height = parameters.get("width", 512), parameters.get("height", 512)
    seconds, fps = parameters.get("duration_seconds", 4), parameters.get("frame_rate", 24)
    if (any(type(v) is not int for v in (width, height, seconds, fps))
            or not 64 <= width <= 1024 or not 64 <= height <= 1024
            or width % 32 or height % 32 or not 1 <= seconds <= 10 or not 1 <= fps <= 30):
        raise ValueError("STUDIO_VIDEO_RECIPE_SIZE_OR_DURATION_INVALID")
    stride = 8 if recipe["recipe_id"] == "comfy-ltx095-video-v1" else 4
    frames = ((seconds * fps - 1 + stride - 1) // stride) * stride + 1
    if not 9 <= frames <= 241 or width * height * frames > 268435456:
        raise ValueError("STUDIO_VIDEO_RECIPE_FRAME_LIMIT")
    seed, negative = parameters.get("seed", 0), parameters.get("negative_prompt", "")
    if type(seed) is not int or not 0 <= seed <= 2147483647 or not isinstance(negative, str) or len(negative) > 8000:
        raise ValueError("STUDIO_VIDEO_RECIPE_PARAMETER_INVALID")
    return {"width": width, "height": height, "frames": frames, "frame_rate": fps,
        "duration_ms": round(frames * 1000 / fps)}


def build_workflow(recipe, prompt, parameters, *, operation="t2v", upload=None):
    if (operation not in recipe["operations"] or not isinstance(prompt, str) or not prompt.strip()
            or len(prompt) > 16000 or (operation == "i2v") != (upload is not None)):
        raise ValueError("STUDIO_VIDEO_RECIPE_INPUT_INVALID")
    t, c, rid = timing(recipe, parameters), recipe["components"], recipe["recipe_id"]
    graph = {}
    if rid == "comfy-ltx095-video-v1":
        graph["4"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": c["model"]}}
        graph["11"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": c["clip"], "type": "ltxv", "device": "default"}}
        model, clip, vae = ["4", 0], ["11", 0], ["4", 2]
    else:
        graph["4"] = {"class_type": "UNETLoader", "inputs": {"unet_name": c["model"], "weight_dtype": "default"}}
        graph["12"] = {"class_type": "VAELoader", "inputs": {"vae_name": c["vae"]}}
        vae, model, clip = ["12", 0], ["13", 0], ["11", 0]
        if rid == "comfy-wan22-ti2v5b-v1":
            graph["11"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": c["clip"], "type": "wan", "device": "default"}}
        elif rid == "comfy-hunyuan10-t2v-v1":
            graph["11"] = {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": c["clip_l"],
                "clip_name2": c["llava"], "type": "hunyuan_video", "device": "default"}}
        else:
            raise ValueError("STUDIO_VIDEO_RECIPE_UNKNOWN")
        graph["13"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": ["4", 0], "shift": 8 if rid == "comfy-wan22-ti2v5b-v1" else 7}}
    graph["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip}}
    graph["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": parameters.get("negative_prompt", ""), "clip": clip}}
    positive, negative, latent = ["6", 0], ["7", 0], ["5", 0]
    size = {"width": t["width"], "height": t["height"], "length": t["frames"], "batch_size": 1}
    if upload is not None:
        graph["20"] = {"class_type": "LoadImage", "inputs": {"image": upload}}
    if rid == "comfy-ltx095-video-v1":
        graph["14"] = {"class_type": "LTXVConditioning", "inputs": {"positive": positive, "negative": negative, "frame_rate": t["frame_rate"]}}
        positive, negative = ["14", 0], ["14", 1]
        if upload is None:
            graph["5"] = {"class_type": "EmptyLTXVLatentVideo", "inputs": size}
        else:
            graph["21"] = {"class_type": "LTXVPreprocess", "inputs": {"image": ["20", 0], "img_compression": 40}}
            graph["5"] = {"class_type": "LTXVImgToVideo", "inputs": {**size, "positive": positive,
                "negative": negative, "vae": vae, "image": ["21", 0], "strength": 1}}
            positive, negative, latent = ["5", 0], ["5", 1], ["5", 2]
        graph["15"] = {"class_type": "LTXVScheduler", "inputs": {"steps": 30, "max_shift": 2.05,
            "base_shift": 0.95, "stretch": True, "terminal": 0.1, "latent": latent}}
        graph["16"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
        graph["3"] = {"class_type": "SamplerCustom", "inputs": {"add_noise": True, "noise_seed": parameters.get("seed", 0),
            "cfg": 3, "model": model, "positive": positive, "negative": negative, "sampler": ["16", 0],
            "sigmas": ["15", 0], "latent_image": latent}}
    elif rid == "comfy-wan22-ti2v5b-v1":
        graph["5"] = {"class_type": "Wan22ImageToVideoLatent", "inputs": {**size, "vae": vae,
            **({"start_image": ["20", 0]} if upload is not None else {})}}
        graph["3"] = {"class_type": "KSampler", "inputs": {"seed": parameters.get("seed", 0), "steps": 20,
            "cfg": 5, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1,
            "model": model, "positive": positive, "negative": negative, "latent_image": latent}}
    else:
        if parameters.get("negative_prompt"):
            raise ValueError("STUDIO_VIDEO_RECIPE_NEGATIVE_PROMPT_UNSUPPORTED")
        graph["5"] = {"class_type": "EmptyHunyuanLatentVideo", "inputs": size}
        graph["14"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": positive, "guidance": 6}}
        graph["15"] = {"class_type": "BasicScheduler", "inputs": {"model": ["4", 0], "scheduler": "simple", "steps": 20, "denoise": 1}}
        graph["16"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}}
        graph["17"] = {"class_type": "BasicGuider", "inputs": {"model": model, "conditioning": ["14", 0]}}
        graph["18"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": parameters.get("seed", 0)}}
        graph["3"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["18", 0], "guider": ["17", 0],
            "sampler": ["16", 0], "sigmas": ["15", 0], "latent_image": latent}}
    graph["8"] = {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": vae}}
    graph["9"] = {"class_type": "SaveWEBM", "inputs": {"images": ["8", 0], "filename_prefix": "AI-Novel-Studio",
        "codec": "vp9", "fps": t["frame_rate"], "crf": 18}}
    return graph


def project_comfy_video_recipe(info, model_name, family):
    try:
        template = next(r for r in RECIPES if r["family"] == family)
        if model_name not in _options(info, template["model_loader"], template["model_input"]):
            return None
        basename = model_name.replace("\\", "/").rsplit("/", 1)[-1]
        c = {"model": model_name}
        if family == "LTX":
            if basename != "ltx-video-2b-v0.9.5.safetensors": return None
            c["clip"] = _component(info, "CLIPLoader", "clip_name", {"t5xxl_fp16.safetensors"})
        elif family == "WAN":
            if basename != "wan2.2_ti2v_5B_fp16.safetensors": return None
            c.update(clip=_component(info, "CLIPLoader", "clip_name", {"umt5_xxl_fp8_e4m3fn_scaled.safetensors"}),
                vae=_component(info, "VAELoader", "vae_name", {"wan2.2_vae.safetensors"}))
        else:
            if basename != "hunyuan_video_t2v_720p_bf16.safetensors": return None
            c.update(clip_l=_component(info, "DualCLIPLoader", "clip_name1", {"clip_l.safetensors"}),
                llava=_component(info, "DualCLIPLoader", "clip_name2", {"llava_llama3_fp8_scaled.safetensors"}),
                vae=_component(info, "VAELoader", "vae_name", {"hunyuan_video_vae_bf16.safetensors"}))
        recipe = {"recipe_id": template["id"], "components": c, "operations": ["t2v"],
            "structural_only": True, "inference_verified": False, "reference_semantics": "SINGLE_IMAGE_INITIALIZATION",
            "reference_video_execution": False, "output_format": "WEBM_VP9"}
        validate_workflow(info, build_workflow(recipe, "structural validation", {}))
        if family != "HUNYUAN_VIDEO":
            trial = {**recipe, "operations": ["t2v", "i2v"]}
            try:
                validate_workflow(info, build_workflow(trial, "structural validation", {}, operation="i2v", upload="source.png"))
            except (ValueError, TypeError, KeyError, IndexError):
                pass
            else:
                recipe["operations"].append("i2v")
        return copy.deepcopy(recipe)
    except (StopIteration, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None
