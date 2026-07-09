import hashlib
import os
import shlex
import subprocess
import sys

from database import PROJECT_ROOT, ensure_directories


AUDIO_DIR = PROJECT_ROOT / "exports" / "audio"
DEFAULT_TTS_VOICE = "en-US-AndrewNeural"
DEFAULT_TTS_RATE = "-13%"
DEFAULT_TTS_PITCH = "+1Hz"
DEFAULT_TTS_VOLUME = "+0%"
MAX_TTS_TEXT_LENGTH = 800
KNOWN_EDGE_TTS_PYTHONS = []


class TtsError(Exception):
    pass


def normalize_tts_text(text):
    normalized = " ".join(str(text or "").split())
    if not normalized:
        raise TtsError("没有可播放的英文内容。")
    if len(normalized) > MAX_TTS_TEXT_LENGTH:
        raise TtsError(f"英文内容过长，当前最多支持 {MAX_TTS_TEXT_LENGTH} 个字符。")
    return normalized


def get_tts_voice():
    return os.environ.get("QUALITY_GLOSSARY_TTS_VOICE", DEFAULT_TTS_VOICE).strip() or DEFAULT_TTS_VOICE


def get_tts_option(name, default_value):
    return os.environ.get(name, default_value).strip() or default_value


def get_tts_settings():
    return {
        "voice": get_tts_voice(),
        "rate": get_tts_option("QUALITY_GLOSSARY_TTS_RATE", DEFAULT_TTS_RATE),
        "pitch": get_tts_option("QUALITY_GLOSSARY_TTS_PITCH", DEFAULT_TTS_PITCH),
        "volume": get_tts_option("QUALITY_GLOSSARY_TTS_VOLUME", DEFAULT_TTS_VOLUME),
    }


def audio_path_for_text(text, settings):
    cache_key = "\0".join(
        [
            settings["voice"],
            settings["rate"],
            settings["pitch"],
            settings["volume"],
            text,
        ]
    )
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:24]
    return AUDIO_DIR / f"{digest}.mp3"


def split_command(command_text):
    return shlex.split(command_text, posix=os.name != "nt")


def build_edge_tts_commands(text, settings, output_path):
    commands = []
    python_candidates = []

    configured_python = os.environ.get("QUALITY_GLOSSARY_EDGE_TTS_PYTHON", "").strip()
    if configured_python:
        python_candidates.append(configured_python)

    for known_python in KNOWN_EDGE_TTS_PYTHONS:
        if os.path.exists(known_python) and known_python not in python_candidates:
            python_candidates.append(known_python)

    if sys.executable not in python_candidates:
        python_candidates.append(sys.executable)

    for python_path in python_candidates:
        commands.append(
            [
                python_path,
                "-m",
                "edge_tts",
                "--voice",
                settings["voice"],
                "--rate",
                settings["rate"],
                "--pitch",
                settings["pitch"],
                "--volume",
                settings["volume"],
                "--text",
                text,
                "--write-media",
                str(output_path),
            ]
        )

    configured_command = os.environ.get("QUALITY_GLOSSARY_EDGE_TTS_COMMAND", "").strip()
    if configured_command:
        commands.append(
            split_command(configured_command)
            + [
                "--voice",
                settings["voice"],
                "--rate",
                settings["rate"],
                "--pitch",
                settings["pitch"],
                "--volume",
                settings["volume"],
                "--text",
                text,
                "--write-media",
                str(output_path),
            ]
        )

    commands.append(
        [
            "edge-tts",
            "--voice",
            settings["voice"],
            "--rate",
            settings["rate"],
            "--pitch",
            settings["pitch"],
            "--volume",
            settings["volume"],
            "--text",
            text,
            "--write-media",
            str(output_path),
        ]
    )

    return commands


def command_label(command):
    if not command:
        return ""
    return " ".join(command[:3])


def summarize_tts_error(output):
    text = " ".join(str(output or "").split())
    lower_text = text.lower()

    if "no module named edge_tts" in lower_text:
        return "这个 Python 环境没有安装 edge_tts"
    if "not recognized" in lower_text or "不是内部或外部命令" in text:
        return "命令不存在"
    if (
        "aiohttp" in lower_text
        or "connect" in lower_text
        or "connection" in lower_text
        or "timed out" in lower_text
        or "timeout" in lower_text
    ):
        return "edge-tts 网络连接失败，请确认网络、VPN 或代理可用"

    if len(text) > 160:
        return text[:160] + "..."
    return text or "生成失败"


def generate_tts_audio(text):
    normalized_text = normalize_tts_text(text)
    settings = get_tts_settings()

    ensure_directories()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    audio_path = audio_path_for_text(normalized_text, settings)
    if audio_path.exists() and audio_path.stat().st_size > 0:
        return {
            "path": audio_path,
            "text": normalized_text,
            **settings,
            "cached": True,
        }

    temp_path = audio_path.with_suffix(".tmp.mp3")
    if temp_path.exists():
        temp_path.unlink()

    timeout = int(os.environ.get("QUALITY_GLOSSARY_TTS_TIMEOUT", "60"))
    errors = []

    for command in build_edge_tts_commands(normalized_text, settings, temp_path):
        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except FileNotFoundError:
            errors.append(f"{command_label(command)}：命令不存在")
            continue
        except subprocess.TimeoutExpired:
            errors.append(f"{command_label(command)}：生成超时")
            continue

        if completed.returncode == 0 and temp_path.exists() and temp_path.stat().st_size > 0:
            temp_path.replace(audio_path)
            return {
                "path": audio_path,
                "text": normalized_text,
                **settings,
                "cached": False,
            }

        stderr = (completed.stderr or completed.stdout or "").strip()
        errors.append(f"{command_label(command)}：{summarize_tts_error(stderr)}")

        if temp_path.exists():
            temp_path.unlink()

    raise TtsError(
        "未能调用 edge-tts。请确认网络、VPN 或代理可用，并建议关闭旧网页服务后用 start_web.bat 重新启动。"
        + (" 失败摘要：" + "；".join(errors[:2]) if errors else "")
    )
