"""Bounded media downloads and real file inspection.

Provider service origins are explicitly supplied by server-owned configuration.
Returned URLs never inherit the legacy global loopback allowlist. DNS addresses
are resolved once and pinned for the connection, including HTTPS SNI validation.
"""
from __future__ import annotations

import http.client
import io
import ipaddress
import json
import math
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlsplit
import wave

from .net_safety import OutboundURLRejected


class MediaValidationError(ValueError):
    pass


def _origin(value: str):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError()
        return parsed, (parsed.scheme, parsed.hostname.lower().rstrip("."), parsed.port or (443 if parsed.scheme == "https" else 80))
    except ValueError as exc:
        raise OutboundURLRejected("invalid media URL") from exc


def media_destination(url: str, configured_provider_endpoint: str | None = None):
    parsed, origin = _origin(url)
    trusted_origin = None
    if configured_provider_endpoint:
        candidate = _origin(configured_provider_endpoint)[1]
        try:
            configured_ip = ipaddress.ip_address(candidate[1])
            configured_ip = getattr(configured_ip,'ipv4_mapped',None) or configured_ip
            configured_local = (configured_ip.is_loopback or configured_ip.is_private) and not configured_ip.is_link_local and not configured_ip.is_unspecified and (not configured_ip.is_reserved or configured_ip.is_loopback)
        except ValueError:
            configured_local = candidate[1] == 'localhost'
        # A cloud hostname must not gain private-network access by rebinding DNS
        # merely because a returned URL uses its configured origin.
        if configured_local: trusted_origin = candidate
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(origin[1], origin[2], type=socket.SOCK_STREAM)})
    except OSError as exc:
        raise OutboundURLRejected("media host could not be resolved") from exc
    if not addresses:
        raise OutboundURLRejected("media host could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        ip = getattr(ip,"ipv4_mapped",None) or ip
        # A configured local service may return files on its own exact origin.
        # Metadata/link-local, multicast and unspecified addresses are never services.
        local_service = origin == trusted_origin and (ip.is_loopback or ip.is_private)
        if ip.is_link_local or ip.is_multicast or ip.is_unspecified or (ip.is_reserved and not (ip.is_loopback and local_service)):
            raise OutboundURLRejected("media destination is restricted")
        if not ip.is_global and not local_service:
            raise OutboundURLRejected("media destination is restricted")
    return parsed, origin, addresses[0]


def fetch_media_bytes(url: str, max_bytes: int, timeout: int = 30, *, configured_provider_endpoint: str | None = None) -> bytes:
    parsed, origin, address = media_destination(url, configured_provider_endpoint)
    connection_type = http.client.HTTPSConnection if origin[0] == "https" else http.client.HTTPConnection
    connection = connection_type(origin[1], origin[2], timeout=timeout)
    # HTTPConnection uses this hook; HTTPSConnection retains original host for SNI.
    connection._create_connection = lambda destination, timeout=None, source_address=None: socket.create_connection((address, origin[2]), timeout, source_address)
    deadline=time.monotonic()+timeout
    try:
        connection.request("GET", (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""), headers={"User-Agent": "AI-Novel-Studio/0.7", "Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200:
            raise OutboundURLRejected("media download requires a direct successful response; redirects are rejected")
        length = response.getheader("Content-Length")
        if length is not None:
            try:
                size = int(length)
            except ValueError as exc:
                raise OutboundURLRejected("invalid media content length") from exc
            if size < 0 or size > max_bytes:
                raise OutboundURLRejected("response exceeds asset size limit")
        if response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}:
            raise OutboundURLRejected("compressed media responses are not supported")
        parts=[];count=0
        read=getattr(response,'read1',response.read)
        while count<=max_bytes:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise OutboundURLRejected('media download timed out')
            stream_socket=connection.sock or getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
            if stream_socket is not None: stream_socket.settimeout(max(0.1,remaining))
            part=read(min(65536,max_bytes+1-count))
            if not part: break
            parts.append(part);count+=len(part)
        data=b''.join(parts)
        if not data or len(data) > max_bytes:
            raise OutboundURLRejected("media response is empty or exceeds asset size limit")
        if length is not None and len(data) != int(length):
            raise OutboundURLRejected("media response is truncated")
        return data
    finally:
        connection.close()


def inspect_media(data: bytes, kind: str) -> dict:
    """Verify actual local bytes, return measured duration and container MIME.

    WAV requires no optional program. Other codecs need the installed ffprobe
    and ffmpeg tools and fail closed if the tools are absent.
    """
    if not data:
        raise MediaValidationError("media is empty")
    if kind == "audio" and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                frames, rate, channels, width = audio.getnframes(), audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
                actual = audio.readframes(frames)
                if not frames or rate <= 0 or len(actual) != frames * channels * width:
                    raise MediaValidationError("WAV data is truncated or empty")
                return {"media_type": "audio/wav", "extension": "wav", "duration_ms": round(frames * 1000 / rate), "sample_rate": rate, "channels": channels, "sample_width": width, "validation": "PCM_DECODED"}
        except (wave.Error, EOFError) as exc:
            raise MediaValidationError("invalid WAV media") from exc
    mp4 = len(data) >= 12 and data[4:8] == b"ftyp"
    webm = data[:4] == b"\x1aE\xdf\xa3"
    mp3 = data[:3] == b"ID3" or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224)
    if kind == "video" and not (mp4 or webm):
        raise MediaValidationError("video container must be MP4 or WebM")
    if kind == "audio" and not (mp4 or webm or mp3 or data[:4] in {b"OggS", b"fLaC"}):
        raise MediaValidationError("unsupported or invalid audio container")
    probe, decoder = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not probe or not decoder:
        raise MediaValidationError("MEDIA_VALIDATOR_NOT_CONFIGURED: ffprobe and ffmpeg are required")
    extension = "mp4" if mp4 else "webm" if webm else "mp3" if mp3 else "ogg" if data[:4] == b"OggS" else "flac"
    with tempfile.TemporaryDirectory(prefix="novel-media-") as directory:
        path = Path(directory) / ("input." + extension)
        path.write_bytes(data)
        try:
            result = subprocess.run([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, timeout=20, check=True)
            details = json.loads(result.stdout)
            streams = [row for row in details.get("streams", []) if row.get("codec_type") == kind]
            duration = float(details.get("format", {}).get("duration") or (streams[0].get("duration") if streams else 0) or 0)
            if not streams or not math.isfinite(duration) or duration <= 0 or duration > 36000:
                raise MediaValidationError("media has no valid playable stream or duration")
            if kind=='video':
                width,height=int(streams[0].get('width',0)),int(streams[0].get('height',0))
                if not 1<=width<=4096 or not 1<=height<=4096 or width*height>16*1024*1024:
                    raise MediaValidationError('video dimensions exceed decoding limit')
            subprocess.run([decoder, "-nostdin", "-v", "error", "-xerror", "-threads", "1", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0" if kind == "video" else "0:a:0", "-f", "null", "-"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30, check=True)
        except (subprocess.SubprocessError, ValueError, OSError) as exc:
            raise MediaValidationError("media decoding failed") from exc
    mime = f"{kind}/{extension}" if extension != "mp3" else "audio/mpeg"
    return {"media_type": mime, "extension": extension, "duration_ms": round(duration * 1000), "validation": "DECODED", "codec": streams[0].get("codec_name")}


def concatenate_wav(parts: list[bytes], pause_ms: int = 0, *, pauses_ms: list[int] | None = None) -> tuple[bytes, list[dict]]:
    """Concatenate measured PCM frames with optional per-boundary silence.

    The scalar API is unchanged. A vector names exactly the boundaries between
    parts; the last segment never adds trailing silence.
    """
    if not parts or len(parts) > 500 or not 0 <= pause_ms <= 3000:
        raise MediaValidationError("invalid audio segment count or pause")
    if pauses_ms is not None and (len(pauses_ms) != len(parts) - 1 or any(
            type(pause) is not int or not 0 <= pause <= 3000 for pause in pauses_ms)):
        raise MediaValidationError("invalid per-segment pauses")
    if sum(len(part) for part in parts) > 64 * 1024 * 1024:
        raise MediaValidationError("audio concatenation input exceeds limit")
    output, manifest, frames, signature = io.BytesIO(), [], 0, None
    with wave.open(output, "wb") as writer:
        for index, data in enumerate(parts):
            info = inspect_media(data, "audio")
            if info["media_type"] != "audio/wav":
                raise MediaValidationError("concatenation currently requires PCM WAV segments")
            with wave.open(io.BytesIO(data), "rb") as reader:
                current = (reader.getnchannels(), reader.getsampwidth(), reader.getframerate())
                if signature is None:
                    signature = current
                    writer.setnchannels(current[0]); writer.setsampwidth(current[1]); writer.setframerate(current[2])
                if current != signature:
                    raise MediaValidationError("audio segments use different PCM formats")
                count = reader.getnframes()
                silence = round(signature[2] * (pause_ms if pauses_ms is None else pauses_ms[index]) / 1000) if index + 1 < len(parts) else 0
                if (frames + count + silence) * signature[0] * signature[1] + 44 > 25 * 1024 * 1024:
                    raise MediaValidationError("audio concatenation output exceeds limit")
                manifest.append({"sequence": index + 1, "start_ms": round(frames * 1000 / signature[2]), "duration_ms": info["duration_ms"]})
                writer.writeframesraw(reader.readframes(count)); frames += count
                if index + 1 < len(parts):
                    writer.writeframesraw((b"\x80" if signature[1] == 1 else b"\x00") * silence * signature[0] * signature[1]); frames += silence
    return output.getvalue(), manifest


def inspect_image(data: bytes) -> dict:
    if data.startswith(b'\x89PNG\r\n\x1a\n'): extension, mime = 'png', 'image/png'
    elif data.startswith(b'\xff\xd8\xff'): extension, mime = 'jpg', 'image/jpeg'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP': extension, mime = 'webp', 'image/webp'
    else: raise MediaValidationError('unsupported or invalid raster image')
    probe, decoder = shutil.which('ffprobe'), shutil.which('ffmpeg')
    if not probe or not decoder: raise MediaValidationError('MEDIA_VALIDATOR_NOT_CONFIGURED')
    with tempfile.TemporaryDirectory(prefix='novel-image-') as directory:
        path=Path(directory)/('image.'+extension);path.write_bytes(data)
        try:
            result=subprocess.run([probe,'-v','error','-protocol_whitelist','file,pipe','-show_streams','-of','json',str(path)],capture_output=True,timeout=10,check=True)
            streams=json.loads(result.stdout).get('streams',[])
            stream=next((row for row in streams if row.get('codec_type')=='video'),{})
            width,height=int(stream.get('width',0)),int(stream.get('height',0))
            if not width or not height or width*height>64*1024*1024:raise MediaValidationError('image dimensions exceed limit')
            subprocess.run([decoder,'-nostdin','-v','error','-xerror','-threads','1','-protocol_whitelist','file,pipe','-i',str(path),'-frames:v','1','-f','null','-'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=15,check=True)
        except (subprocess.SubprocessError,ValueError,OSError) as exc:raise MediaValidationError('image decoding failed') from exc
    return {'extension':extension,'media_type':mime,'width':width,'height':height,'validation':'DECODED'}
