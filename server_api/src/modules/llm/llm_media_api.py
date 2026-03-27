"""STT, TTS, 이미지 생성을 담당하는 미디어용 FastAPI 핸들러."""

import io
import os
import shutil
import tempfile

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from .services.openai_service import get_openai_client, to_bool

media_router = APIRouter(tags=["llm"])

ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".webm", ".mp4", ".mpeg", ".mpga", ".ogg"}
ALLOWED_AUDIO_FORMATS = {"mp3", "wav", "opus", "flac", "aac", "pcm"}
ALLOWED_IMAGE_SIZES = {"1024x1024", "1024x1536", "1536x1024"}


@media_router.post("/stt")
async def stt(
    file: UploadFile = File(...),
    provider: str = Form("openai"),
    language: str = Form(""),
    prompt: str = Form(""),
    translate_to_english: str = Form("false"),
):
    provider = (provider or "openai").lower()
    if provider != "openai":
        return {"text": "", "error": "STT is currently available only for the OpenAI provider."}

    client, err = get_openai_client()
    if err:
        return {"text": "", "error": err}

    do_translate = to_bool(translate_to_english)

    suffix = (os.path.splitext(file.filename or "audio.webm")[1] or ".webm").lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        suffix = ".webm"

    max_audio_bytes = int(os.getenv("MAX_AUDIO_BYTES", str(20 * 1024 * 1024)))
    min_audio_bytes = int(os.getenv("MIN_AUDIO_BYTES", "1500"))
    temp_path = None

    try:
        # OpenAI 오디오 API는 실제 파일 핸들을 기대하고,
        # 최종 바이트 크기 검증도 필요하므로 임시 파일로 한 번 저장한다.
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp_path = temp.name
            shutil.copyfileobj(file.file, temp)

        audio_size = os.path.getsize(temp_path)
        if audio_size < min_audio_bytes:
            return {"text": "", "error": "The audio file is too short. Please try speaking for at least 1 to 2 seconds."}
        if audio_size > max_audio_bytes:
            return {"text": "", "error": f"The audio file is too large. Maximum size is {max_audio_bytes // (1024 * 1024)}MB."}

        model_name = os.getenv("OPENAI_STT_MODEL", "gpt-4o-mini-transcribe")

        def run_stt(use_optional: bool):
            with open(temp_path, "rb") as audio:
                kwargs = {"model": model_name, "file": audio}
                if use_optional:
                    if language:
                        kwargs["language"] = language
                    if prompt:
                        kwargs["prompt"] = prompt
                if do_translate:
                    return client.audio.translations.create(**kwargs)
                return client.audio.transcriptions.create(**kwargs)

        try:
            transcript = run_stt(use_optional=True)
        except Exception as exc:
            message = str(exc)
            # 일부 파일은 `language`/`prompt` 같은 옵션 조합을 거부하므로
            # 최소 인자만 남겨 한 번 더 재시도한다.
            if "invalid_value" in message or "corrupted or unsupported" in message.lower():
                transcript = run_stt(use_optional=False)
            else:
                raise

        return {
            "text": getattr(transcript, "text", "") or "",
            "error": "",
            "detected_language": getattr(transcript, "language", "") or "",
        }
    except Exception as exc:
        return {"text": "", "error": str(exc)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@media_router.post("/tts")
async def tts(
    text: str = Form(""),
    provider: str = Form("openai"),
    voice: str = Form("alloy"),
    audio_format: str = Form("mp3"),
    speed: str = Form("1.0"),
):
    content = (text or "").strip()
    if not content:
        return {"error": "Text is required for TTS."}

    provider = (provider or "openai").lower()
    if provider != "openai":
        return {"error": "TTS is currently available only for the OpenAI provider."}

    client, err = get_openai_client()
    if err:
        return {"error": err}

    voice_name = (voice or "alloy").strip().lower()
    out_format = (audio_format or "mp3").strip().lower()
    if out_format not in ALLOWED_AUDIO_FORMATS:
        out_format = "mp3"

    try:
        speed_value = float(speed)
    except Exception:
        speed_value = 1.0
    speed_value = max(0.25, min(4.0, speed_value))

    try:
        response = client.audio.speech.create(
            model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            voice=voice_name,
            input=content,
            response_format=out_format,
            speed=speed_value,
        )
        payload = response.read()
        if not payload:
            return {"error": "TTS generation returned no audio."}
        media_type = "audio/mpeg" if out_format == "mp3" else f"audio/{out_format}"
        return StreamingResponse(io.BytesIO(payload), media_type=media_type, headers={"Cache-Control": "no-cache"})
    except Exception as exc:
        return {"error": str(exc)}


@media_router.post("/image")
async def generate_image(
    prompt: str = Form(""),
    provider: str = Form("openai"),
    size: str = Form("1024x1024"),
):
    text = (prompt or "").strip()
    if not text:
        return {"error": "Prompt is required for image generation."}

    provider = (provider or "openai").lower()
    if provider != "openai":
        return {"error": "Image generation is currently available only for the OpenAI provider."}

    client, err = get_openai_client()
    if err:
        return {"error": err}

    image_size = size if size in ALLOWED_IMAGE_SIZES else "1024x1024"

    primary_model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    fallback_models = [model for model in [primary_model, "dall-e-3"] if model]
    tried = set()
    last_error = ""

    for model in fallback_models:
        if model in tried:
            continue
        tried.add(model)
        try:
            # 환경별 API 버전이나 모델 지원 상태가 다를 수 있어
            # 이미지 생성은 호환용 폴백 모델까지 순서대로 시도한다.
            kwargs = {"model": model, "prompt": text, "size": image_size}
            if model == "dall-e-3":
                kwargs["quality"] = "standard"
                kwargs["style"] = "natural"
                kwargs["n"] = 1

            result = client.images.generate(**kwargs)
            data = getattr(result, "data", None) or []
            if not data:
                return {"error": "Image generation returned no data."}

            item = data[0]
            b64 = getattr(item, "b64_json", None)
            url = getattr(item, "url", None)
            if b64:
                return {"error": "", "image_data_url": f"data:image/png;base64,{b64}", "model": model}
            if url:
                return {"error": "", "image_url": url, "model": model}
            return {"error": "The image response format was not recognized."}
        except Exception as exc:
            last_error = str(exc)

    return {"error": last_error or "Image generation failed."}
