"""Bounded media downloads and real file inspection.

Provider service origins are explicitly supplied by server-owned configuration.
Returned URLs never inherit the legacy global loopback allowlist. DNS addresses
are resolved once and pinned for the connection, including HTTPS SNI validation.
"""
from __future__ import annotations

from contextlib import contextmanager
import http.client
import io
import ipaddress
import json
import math
import os
from pathlib import Path
import shutil
import socket
import stat
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


def _owned_empty_media_directory(path, identity):
    """Only the same private, ordinary empty directory can await sharing release."""
    try:
        current = path.lstat()
        if (identity is None or not current.st_ino or
                (current.st_dev, current.st_ino) != identity or
                not stat.S_ISDIR(current.st_mode) or
                getattr(current, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            return False
        with os.scandir(path) as entries:
            return next(entries, None) is None
    except OSError:
        return False


def _cleanup_media_directory(temporary, identity):
    path = Path(temporary.name)
    previous_error = None
    for attempt in range(3):
        # The bounded wait is an interleaving boundary. Revalidate immediately
        # before retrying so a replaced directory or later content is untouched.
        if attempt and not _owned_empty_media_directory(path, identity):
            raise previous_error
        try:
            temporary.cleanup()
            return
        except OSError as error:
            # Reaped Windows children can leave a briefly shared empty CWD.
            # No other failure, replaced directory or nonempty tree retries.
            if (attempt == 2 or os.name != "nt" or getattr(error, "winerror", None) != 32
                    or not _owned_empty_media_directory(path, identity)):
                raise
            previous_error = error
            time.sleep((0.025, 0.05)[attempt])


@contextmanager
def _media_inspection_directory():
    temporary = tempfile.TemporaryDirectory(prefix="novel-media-")
    identity = None
    try:
        created = Path(temporary.name).lstat()
        identity = (created.st_dev, created.st_ino)
        yield temporary.name
    finally:
        _cleanup_media_directory(temporary, identity)


def inspect_media(data: bytes, kind: str, *, guard=None) -> dict:
    """Verify actual local bytes, return measured duration and container MIME.

    WAV requires no optional program. Other codecs need the installed ffprobe
    and ffmpeg tools and fail closed if the tools are absent.
    """
    # A guard may raise ValueError (including AudiobookError), OSError or a
    # process exception itself. Preserve its exact exception rather than
    # reporting revocation/cancellation as malformed media.
    guard_failure = None
    def current():
        nonlocal guard_failure
        if guard is not None:
            try:
                guard()
            except BaseException as error:
                guard_failure = error
                raise
    current()
    if not data:
        raise MediaValidationError("media is empty")
    if kind == "audio" and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                frames, rate, channels, width = audio.getnframes(), audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
                actual = audio.readframes(frames)
                if not frames or rate <= 0 or len(actual) != frames * channels * width:
                    raise MediaValidationError("WAV data is truncated or empty")
                current()
                return {"media_type": "audio/wav", "extension": "wav", "duration_ms": round(frames * 1000 / rate), "sample_rate": rate, "channels": channels, "sample_width": width, "validation": "PCM_DECODED"}
        except (wave.Error, EOFError) as exc:
            if exc is guard_failure:
                raise
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
    # Local import avoids the original export owner's MediaValidationError
    # dependency creating a top-level circular import. Do not duplicate its
    # bounded capture, cancellation, termination or reaping implementation.
    from .services.studio_timeline_export import run_guarded_process
    try:
        with _media_inspection_directory() as directory:
            path = Path(directory) / ("input." + extension)
            output = Path(directory) / "probe.json"
            path.write_bytes(data)
            run_guarded_process([probe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams", "-show_format", "-of", "json", str(path)],
                cwd=directory, guard=current, timeout=20, stdout_path=output)
            # JSON, its shape and all fields used below are untrusted native
            # output. Validate before indexing/converting or starting decode.
            def invalid_constant(value):
                raise ValueError("non-finite JSON constant")
            details = json.loads(output.read_text(encoding="utf-8"), parse_constant=invalid_constant)
            if (not isinstance(details, dict) or not isinstance(details.get("streams"), list)
                    or not isinstance(details.get("format", {}), dict)
                    or any(not isinstance(row, dict) for row in details["streams"])):
                raise ValueError("invalid media probe structure")
            streams = [row for row in details["streams"] if row.get("codec_type") == kind]
            durations = [details.get("format", {}).get("duration"), streams[0].get("duration") if streams else None]
            if any(value is not None and type(value) not in (str, int, float) for value in durations):
                raise ValueError("invalid media duration")
            raw_duration = durations[0] or durations[1] or 0
            if type(raw_duration) not in (str, int, float):
                raise ValueError("invalid media duration")
            duration = float(raw_duration)
            if not streams or not math.isfinite(duration) or duration <= 0 or duration > 36000:
                raise ValueError("media has no valid playable stream or duration")
            if streams[0].get("codec_name") is not None and not isinstance(streams[0]["codec_name"], str):
                raise ValueError("invalid media codec")
            if kind == "video":
                dimensions = [streams[0].get(name, 0) for name in ("width", "height")]
                if any(type(value) not in (str, int) for value in dimensions):
                    raise ValueError("invalid video dimensions")
                width, height = map(int, dimensions)
                if not 1 <= width <= 4096 or not 1 <= height <= 4096 or width * height > 16 * 1024 * 1024:
                    raise ValueError("video dimensions exceed decoding limit")
            current()
            run_guarded_process([decoder, "-nostdin", "-v", "error", "-xerror", "-threads", "1", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0" if kind == "video" else "0:a:0", "-f", "null", "-"],
                cwd=directory, guard=current, timeout=30)
            current()
    except (subprocess.SubprocessError, ValueError, OSError, RecursionError, OverflowError) as exc:
        if exc is guard_failure:
            raise
        if guard_failure is not None:
            # Preserve the original authority exception even when strict
            # cleanup also fails. Record that failure without exposing paths.
            guard_failure.add_note("Media inspection temporary directory cleanup did not complete.")
            raise guard_failure from MediaValidationError("media temporary directory cleanup failed")
        # Never expose private paths, argv or captured native diagnostics.
        raise MediaValidationError("media decoding failed") from None
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
