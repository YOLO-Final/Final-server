import asyncio
import base64
import os
import time
from binascii import Error as BinasciiError

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.lib.database import get_db
from src.modules.vision.db.schema import CameraDeviceInfoRequest, OnpremHandshakeRequest, OverlayTodayCountsResponse
from src.modules.vision.service import (
    build_mjpeg_chunk,
    get_latest_frame,
    get_most_recent_camera_id,
    get_onprem_handshake,
    get_today_overlay_counts,
    ingest_overlay_frame,
    list_camera_states,
    register_camera_device,
    register_onprem_handshake,
    vision_status_placeholder,
)

router = APIRouter(prefix="/vision", tags=["vision"])


@router.get("/status")
def vision_status():
    return vision_status_placeholder()


@router.get("/stream/state")
def legacy_stream_state():
    return {
        "ok": True,
        "module": "vision",
        "state": "ready",
        "cameras": list_camera_states(),
    }


@router.api_route("/stream/heartbeat", methods=["GET", "POST"])
def legacy_stream_heartbeat():
    return {
        "ok": True,
        "heartbeat": "alive",
        "ts": time.time(),
        "camera_count": len(list_camera_states()),
    }


@router.get("/interop/ping")
def interop_ping():
    return {"ok": True, "module": "vision", "status": "alive"}


@router.get("/cameras")
def list_cameras():
    return {"items": list_camera_states()}


@router.get("/overlay-counts/today", response_model=OverlayTodayCountsResponse)
def get_overlay_today_counts(db: Session = Depends(get_db)):
    return get_today_overlay_counts(db=db)


def _to_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _verify_camera_token(x_camera_token: str | None, x_api_token: str | None = None):
    allow_no_token = _to_bool(os.getenv("VISION_ALLOW_NO_TOKEN"))
    expected_token = (os.getenv("VISION_CAMERA_TOKEN") or os.getenv("VISION_API_TOKEN") or "").strip()
    provided_token = (x_camera_token or x_api_token or "").strip()

    if allow_no_token:
        return

    # If server token is not configured, accept requests for local/dev interop.
    if not expected_token:
        return

    if provided_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid camera token.")


@router.post("/cameras/{camera_id}/device")
def register_camera_device_info(
    payload: CameraDeviceInfoRequest,
    request: Request,
    camera_id: str = Path(..., min_length=1, max_length=64),
    x_camera_token: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
):
    _verify_camera_token(x_camera_token, x_api_token)

    client_host = request.client.host if request.client else ""
    try:
        result = register_camera_device(
            camera_id=camera_id,
            payload=payload.model_dump(),
            remote_ip=client_host,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"ok": True, **result}


@router.post("/interop/handshake")
def onprem_handshake(
    payload: OnpremHandshakeRequest,
    request: Request,
    x_camera_token: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
):
    _verify_camera_token(x_camera_token, x_api_token)

    camera_id = (payload.camera_id or "").strip()
    if not camera_id:
        raise HTTPException(status_code=400, detail="camera_id is required.")

    client_host = request.client.host if request.client else ""
    try:
        result = register_onprem_handshake(
            camera_id=camera_id,
            payload=payload.model_dump(),
            remote_ip=client_host,
        )
        register_camera_device(
            camera_id=camera_id,
            payload=payload.model_dump(),
            remote_ip=client_host,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"ok": True, "message": "handshake accepted", "handshake": result}


@router.get("/interop/handshake/{camera_id}")
def get_handshake(camera_id: str = Path(..., min_length=1, max_length=64)):
    state = get_onprem_handshake(camera_id)
    if not state:
        raise HTTPException(status_code=404, detail="handshake not found")
    return {"ok": True, "handshake": state}


@router.post("/cameras/{camera_id}/frames")
async def ingest_camera_frame(
    camera_id: str = Path(..., min_length=1, max_length=64),
    file: UploadFile = File(...),
    x_camera_token: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
):
    _verify_camera_token(x_camera_token, x_api_token)

    content_type = (file.content_type or "").lower()
    if content_type not in {"image/jpeg", "image/jpg", "image/png"}:
        raise HTTPException(status_code=400, detail="Only image/jpeg or image/png is supported.")

    payload = await file.read()
    max_frame_bytes = int(os.getenv("VISION_MAX_FRAME_BYTES", str(3 * 1024 * 1024)))
    if len(payload) > max_frame_bytes:
        raise HTTPException(status_code=413, detail=f"Frame too large. Max bytes: {max_frame_bytes}")

    try:
        # Default mode: on-prem already processed and overlaid the frame.
        result = await asyncio.to_thread(ingest_overlay_frame, camera_id, payload, 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Vision processing failed: {exc}") from exc

    return {"ok": True, **result}


def _decode_base64_payload(value: str) -> bytes:
    payload = (value or "").strip()
    if not payload:
        return b""
    if "," in payload:
        payload = payload.split(",", 1)[1]
    try:
        return base64.b64decode(payload, validate=True)
    except (ValueError, BinasciiError) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image payload.") from exc


@router.post("/inspect")
async def legacy_inspect(
    request: Request,
    file: UploadFile | None = File(default=None),
    camera_id: str = Form(""),
    x_camera_token: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
):
    _verify_camera_token(x_camera_token, x_api_token)

    normalized_camera_id = (camera_id or "").strip()
    payload_bytes = b""
    normalized_detected_count = 0

    content_type = (request.headers.get("content-type") or "").lower()

    if file is not None:
        normalized_camera_id = normalized_camera_id or "onprem-default"
        payload_bytes = await file.read()
    elif "application/json" in content_type:
        body = await request.json()
        normalized_camera_id = (
            normalized_camera_id
            or str(body.get("camera_id") or body.get("cameraId") or "").strip()
            or "onprem-default"
        )
        normalized_detected_count = int(body.get("detected_count") or body.get("face_count") or 0)

        raw_base64 = (
            body.get("overlay_image_base64")
            or body.get("overlayImageBase64")
            or body.get("image_base64")
            or body.get("imageBase64")
            or body.get("frame_base64")
            or body.get("frameBase64")
            or body.get("image")
            or body.get("frame")
            or ""
        )
        payload_bytes = _decode_base64_payload(str(raw_base64))
    else:
        normalized_camera_id = normalized_camera_id or "onprem-default"
        payload_bytes = await request.body()

    if not payload_bytes:
        raise HTTPException(
            status_code=422,
            detail="No frame payload. Send multipart file or JSON image_base64/frame_base64.",
        )

    try:
        result = await asyncio.to_thread(
            ingest_overlay_frame,
            normalized_camera_id,
            payload_bytes,
            normalized_detected_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Vision processing failed: {exc}") from exc

    result = {"ok": True, **result}
    overlay_image_base64 = ""
    overlay_image_data_url = ""
    latest_state = get_latest_frame(normalized_camera_id)
    if latest_state and latest_state.jpeg_bytes:
        encoded = base64.b64encode(latest_state.jpeg_bytes).decode("ascii")
        overlay_image_base64 = encoded
        overlay_image_data_url = f"data:image/jpeg;base64,{encoded}"

    return {
        **result,
        "overlay_url": f"/api/v1/vision/cameras/{normalized_camera_id}/stream.mjpeg",
        "overlay_fallback_url": f"/api/v1/vision/cameras/{normalized_camera_id}/stream",
        "overlay_image_base64": overlay_image_base64,
        "overlay_image_data_url": overlay_image_data_url,
    }


@router.get("/cameras/{camera_id}/stream.mjpeg")
async def stream_camera_overlay(camera_id: str = Path(..., min_length=1, max_length=64)):
    async def generator():
        while True:
            state = get_latest_frame(camera_id)
            if state is None:
                await asyncio.sleep(0.1)
                continue

            yield build_mjpeg_chunk(state.jpeg_bytes)
            await asyncio.sleep(0.04)

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers=headers,
    )


@router.get("/cameras/{camera_id}/stream")
async def stream_camera_overlay_alias(camera_id: str = Path(..., min_length=1, max_length=64)):
    return await stream_camera_overlay(camera_id=camera_id)


@router.api_route("/overlay", methods=["GET", "POST"])
async def legacy_overlay(request: Request, camera_id: str = Query(default="")):
    if request.method == "POST":
        return {
            "ok": True,
            "message": "Use GET /api/v1/vision/overlay for MJPEG stream.",
            "overlay_url": "/api/v1/vision/overlay",
        }

    normalized_camera_id = (camera_id or "").strip() or get_most_recent_camera_id()
    if not normalized_camera_id:
        raise HTTPException(status_code=404, detail="No camera stream available yet.")
    return await stream_camera_overlay(camera_id=normalized_camera_id)


@router.post("/interop/cameras/{camera_id}/frames")
async def interop_ingest_camera_frame(
    camera_id: str = Path(..., min_length=1, max_length=64),
    file: UploadFile = File(...),
    x_camera_token: str | None = Header(default=None),
    x_api_token: str | None = Header(default=None),
):
    return await ingest_camera_frame(
        camera_id=camera_id,
        file=file,
        x_camera_token=x_camera_token,
        x_api_token=x_api_token,
    )


@router.get("/interop/cameras/{camera_id}/overlay")
async def interop_stream_overlay(camera_id: str = Path(..., min_length=1, max_length=64)):
    return await stream_camera_overlay(camera_id=camera_id)
