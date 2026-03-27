import os
import time
from datetime import date
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.modules.auth.vision.service import FaceEngineUnavailableError, _get_face_analyzer


@dataclass
class CameraFrameState:
    jpeg_bytes: bytes
    updated_at: float
    width: int
    height: int
    face_count: int


@dataclass
class CameraDeviceState:
    camera_id: str
    device_name: str
    user_agent: str
    os: str
    browser_language: str
    viewport: str
    screen: str
    timezone: str
    platform: str
    cpu_cores: int
    memory_gb: float
    network_type: str
    network_downlink_mbps: float
    local_ip_hint: str
    remote_ip: str
    first_seen_at: float
    last_seen_at: float
    last_frame_at: float


_camera_frames: dict[str, CameraFrameState] = {}
_camera_devices: dict[str, CameraDeviceState] = {}
_interop_handshakes: dict[str, dict[str, Any]] = {}
_camera_lock = Lock()
_pcb_model_lock = Lock()
_pcb_model: Any = None
_pcb_model_loaded = False
_pcb_model_error = ""


def _normalize_text(value: Any, max_len: int = 200) -> str:
    text = str(value or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _normalize_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return default


def _normalize_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def _get_pcb_model_path() -> Path:
    return Path(__file__).resolve().parent / "model" / "pcb_best.pt"


def _get_pcb_model() -> Any:
    global _pcb_model, _pcb_model_loaded, _pcb_model_error

    if _pcb_model_loaded:
        return _pcb_model

    with _pcb_model_lock:
        if _pcb_model_loaded:
            return _pcb_model

        model_path = _get_pcb_model_path()
        if not model_path.exists():
            _pcb_model_error = f"Model file not found: {model_path}"
            _pcb_model_loaded = True
            _pcb_model = None
            return None

        try:
            from ultralytics import YOLO  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            _pcb_model_error = f"Ultralytics is not available: {exc}"
            _pcb_model_loaded = True
            _pcb_model = None
            return None

        try:
            _pcb_model = YOLO(str(model_path))
            _pcb_model_error = ""
        except Exception as exc:  # noqa: BLE001
            _pcb_model_error = f"PCB model load failed: {exc}"
            _pcb_model = None

        _pcb_model_loaded = True
        return _pcb_model


def get_pcb_model_status() -> dict[str, Any]:
    model_path = _get_pcb_model_path()
    model = _get_pcb_model()
    return {
        "path": str(model_path),
        "exists": model_path.exists(),
        "loaded": _pcb_model_loaded,
        "available": model is not None,
        "error": _pcb_model_error,
    }


def _overlay_pcb_predictions(image):
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise FaceEngineUnavailableError("OpenCV is not available in the API container.") from exc

    model = _get_pcb_model()
    if model is None:
        if _pcb_model_error:
            cv2.putText(
                image,
                "PCB model unavailable",
                (10, 52),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (80, 80, 255),
                2,
                cv2.LINE_AA,
            )
        return image, 0

    conf_thres = _normalize_float(os.getenv("VISION_PCB_CONF", "0.25"), 0.25)
    iou_thres = _normalize_float(os.getenv("VISION_PCB_IOU", "0.45"), 0.45)
    imgsz = _normalize_int(os.getenv("VISION_PCB_IMGSZ", "640"), 640)

    try:
        results = model.predict(
            source=image,
            verbose=False,
            conf=max(0.01, min(conf_thres, 0.95)),
            iou=max(0.01, min(iou_thres, 0.95)),
            imgsz=max(320, min(imgsz, 1280)),
            device="cpu",
        )
    except Exception as exc:  # noqa: BLE001
        cv2.putText(
            image,
            "PCB inference failed",
            (10, 52),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (80, 80, 255),
            2,
            cv2.LINE_AA,
        )
        print(f"[vision] PCB inference error: {exc}")
        return image, 0

    if not results:
        return image, 0

    result = results[0]
    names = getattr(result, "names", None) or getattr(model, "names", {}) or {}
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return image, 0

    count = 0
    try:
        xyxy_list = boxes.xyxy.tolist()
        conf_list = boxes.conf.tolist()
        cls_list = boxes.cls.tolist()
    except Exception:  # noqa: BLE001
        return image, 0

    for xyxy, score, cls_idx in zip(xyxy_list, conf_list, cls_list):
        if len(xyxy) < 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in xyxy[:4]]
        class_id = int(cls_idx)
        class_name = str(names.get(class_id, f"cls_{class_id}"))
        label = f"{class_name} {float(score):.2f}"

        cv2.rectangle(image, (x1, y1), (x2, y2), (45, 160, 255), 2)
        cv2.putText(
            image,
            label,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (45, 160, 255),
            2,
            cv2.LINE_AA,
        )
        count += 1

    return image, count


def register_camera_device(camera_id: str, payload: dict[str, Any], remote_ip: str = "") -> dict[str, Any]:
    normalized_camera_id = (camera_id or "").strip()
    if not normalized_camera_id:
        raise ValueError("camera_id is required.")

    now = time.time()
    with _camera_lock:
        existing = _camera_devices.get(normalized_camera_id)
        first_seen = existing.first_seen_at if existing else now

        state = CameraDeviceState(
            camera_id=normalized_camera_id,
            device_name=_normalize_text(payload.get("device_name") or payload.get("hostname") or "onprem-device", 120),
            user_agent=_normalize_text(payload.get("user_agent"), 400),
            os=_normalize_text(payload.get("os"), 80),
            browser_language=_normalize_text(payload.get("browser_language") or payload.get("language"), 32),
            viewport=_normalize_text(payload.get("viewport"), 40),
            screen=_normalize_text(payload.get("screen"), 40),
            timezone=_normalize_text(payload.get("timezone"), 80),
            platform=_normalize_text(payload.get("platform"), 80),
            cpu_cores=max(0, _normalize_int(payload.get("cpu_cores"), 0)),
            memory_gb=max(0.0, _normalize_float(payload.get("memory_gb"), 0.0)),
            network_type=_normalize_text(payload.get("network_type"), 32),
            network_downlink_mbps=max(0.0, _normalize_float(payload.get("network_downlink_mbps"), 0.0)),
            local_ip_hint=_normalize_text(payload.get("local_ip_hint"), 80),
            remote_ip=_normalize_text(remote_ip, 80),
            first_seen_at=first_seen,
            last_seen_at=now,
            last_frame_at=existing.last_frame_at if existing else 0.0,
        )
        _camera_devices[normalized_camera_id] = state

    return {
        "camera_id": state.camera_id,
        "device_name": state.device_name,
        "os": state.os,
        "browser_language": state.browser_language,
        "platform": state.platform,
        "remote_ip": state.remote_ip,
        "first_seen_at": state.first_seen_at,
        "last_seen_at": state.last_seen_at,
    }


def register_onprem_handshake(camera_id: str, payload: dict[str, Any], remote_ip: str = "") -> dict[str, Any]:
    normalized_camera_id = (camera_id or "").strip()
    if not normalized_camera_id:
        raise ValueError("camera_id is required.")

    now = time.time()
    with _camera_lock:
        previous = _interop_handshakes.get(normalized_camera_id) or {}
        first_seen_at = float(previous.get("first_seen_at", now))
        state = {
            "camera_id": normalized_camera_id,
            "site_id": _normalize_text(payload.get("site_id"), 120),
            "agent_version": _normalize_text(payload.get("agent_version"), 80),
            "device_name": _normalize_text(payload.get("device_name"), 120),
            "os": _normalize_text(payload.get("os"), 80),
            "platform": _normalize_text(payload.get("platform"), 80),
            "user_agent": _normalize_text(payload.get("user_agent"), 400),
            "browser_language": _normalize_text(payload.get("browser_language"), 32),
            "viewport": _normalize_text(payload.get("viewport"), 40),
            "screen": _normalize_text(payload.get("screen"), 40),
            "timezone": _normalize_text(payload.get("timezone"), 80),
            "cpu_cores": max(0, _normalize_int(payload.get("cpu_cores"), 0)),
            "memory_gb": max(0.0, _normalize_float(payload.get("memory_gb"), 0.0)),
            "network_type": _normalize_text(payload.get("network_type"), 32),
            "network_downlink_mbps": max(0.0, _normalize_float(payload.get("network_downlink_mbps"), 0.0)),
            "local_ip_hint": _normalize_text(payload.get("local_ip_hint"), 80),
            "remote_ip": _normalize_text(remote_ip, 80),
            "first_seen_at": first_seen_at,
            "last_seen_at": now,
        }
        _interop_handshakes[normalized_camera_id] = state
    return state


def get_onprem_handshake(camera_id: str) -> dict[str, Any] | None:
    normalized_camera_id = (camera_id or "").strip()
    if not normalized_camera_id:
        return None
    with _camera_lock:
        return _interop_handshakes.get(normalized_camera_id)


def _decode_image(raw_bytes: bytes):
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise FaceEngineUnavailableError("OpenCV or NumPy is not available in the API container.") from exc

    image_array = np.frombuffer(raw_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Failed to decode image data.")
    return image


def _encode_jpeg(image, quality: int = 85) -> bytes:
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise FaceEngineUnavailableError("OpenCV is not available in the API container.") from exc

    success, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        raise ValueError("Failed to encode image as jpeg.")
    return encoded.tobytes()


def _overlay_faces(image):
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise FaceEngineUnavailableError("OpenCV is not available in the API container.") from exc

    image, pcb_count = _overlay_pcb_predictions(image)
    if pcb_count <= 0:
        try:
            analyzer = _get_face_analyzer()
            faces = analyzer.get(image)
        except FaceEngineUnavailableError:
            faces = []

        for face in faces:
            x1, y1, x2, y2 = [int(value) for value in face.bbox]
            cv2.rectangle(image, (x1, y1), (x2, y2), (50, 220, 50), 2)
            cv2.putText(
                image,
                "face",
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (50, 220, 50),
                2,
                cv2.LINE_AA,
            )
        detected_count = len(faces)
    else:
        detected_count = pcb_count

    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    cv2.putText(
        image,
        f"overlay@{now}",
        (10, 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 210, 40),
        2,
        cv2.LINE_AA,
    )

    return image, detected_count


def process_camera_frame(camera_id: str, frame_bytes: bytes) -> dict:
    normalized_camera_id = (camera_id or "").strip()
    if not normalized_camera_id:
        raise ValueError("camera_id is required.")
    if not frame_bytes:
        raise ValueError("frame payload is empty.")

    image = _decode_image(frame_bytes)
    overlaid_image, face_count = _overlay_faces(image)
    jpeg_bytes = _encode_jpeg(overlaid_image)

    height, width = overlaid_image.shape[:2]
    state = CameraFrameState(
        jpeg_bytes=jpeg_bytes,
        updated_at=time.time(),
        width=width,
        height=height,
        face_count=face_count,
    )

    with _camera_lock:
        _camera_frames[normalized_camera_id] = state
        if normalized_camera_id in _camera_devices:
            _camera_devices[normalized_camera_id].last_seen_at = state.updated_at
            _camera_devices[normalized_camera_id].last_frame_at = state.updated_at

    return {
        "camera_id": normalized_camera_id,
        "width": width,
        "height": height,
        "face_count": face_count,
        "updated_at": state.updated_at,
    }


def ingest_overlay_frame(camera_id: str, frame_bytes: bytes, detected_count: int = 0) -> dict:
    normalized_camera_id = (camera_id or "").strip()
    if not normalized_camera_id:
        raise ValueError("camera_id is required.")
    if not frame_bytes:
        raise ValueError("frame payload is empty.")

    # On-prem already computed and overlaid the frame. Server just decodes/normalizes and relays.
    image = _decode_image(frame_bytes)
    jpeg_bytes = _encode_jpeg(image)

    height, width = image.shape[:2]
    state = CameraFrameState(
        jpeg_bytes=jpeg_bytes,
        updated_at=time.time(),
        width=width,
        height=height,
        face_count=max(0, int(detected_count or 0)),
    )

    with _camera_lock:
        _camera_frames[normalized_camera_id] = state
        if normalized_camera_id in _camera_devices:
            _camera_devices[normalized_camera_id].last_seen_at = state.updated_at
            _camera_devices[normalized_camera_id].last_frame_at = state.updated_at

    return {
        "camera_id": normalized_camera_id,
        "width": width,
        "height": height,
        "face_count": state.face_count,
        "updated_at": state.updated_at,
        "mode": "onprem-overlay",
    }


def get_latest_frame(camera_id: str) -> CameraFrameState | None:
    normalized_camera_id = (camera_id or "").strip()
    if not normalized_camera_id:
        return None

    with _camera_lock:
        return _camera_frames.get(normalized_camera_id)


def get_most_recent_camera_id() -> str:
    with _camera_lock:
        if not _camera_frames:
            return ""
        return max(_camera_frames.items(), key=lambda item: item[1].updated_at)[0]


def list_camera_states() -> list[dict]:
    with _camera_lock:
        camera_ids = sorted(set(_camera_frames.keys()) | set(_camera_devices.keys()))
        items: list[dict] = []
        for camera_id in camera_ids:
            frame_state = _camera_frames.get(camera_id)
            device_state = _camera_devices.get(camera_id)
            items.append(
                {
                    "camera_id": camera_id,
                    "updated_at": frame_state.updated_at if frame_state else 0.0,
                    "width": frame_state.width if frame_state else 0,
                    "height": frame_state.height if frame_state else 0,
                    "face_count": frame_state.face_count if frame_state else 0,
                    "device": {
                        "device_name": device_state.device_name if device_state else "",
                        "os": device_state.os if device_state else "",
                        "browser_language": device_state.browser_language if device_state else "",
                        "platform": device_state.platform if device_state else "",
                        "timezone": device_state.timezone if device_state else "",
                        "remote_ip": device_state.remote_ip if device_state else "",
                        "first_seen_at": device_state.first_seen_at if device_state else 0.0,
                        "last_seen_at": device_state.last_seen_at if device_state else 0.0,
                        "last_frame_at": device_state.last_frame_at if device_state else 0.0,
                    },
                }
            )
        return items


def build_mjpeg_chunk(jpeg_bytes: bytes) -> bytes:
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        + f"Content-Length: {len(jpeg_bytes)}\r\n\r\n".encode("ascii")
        + jpeg_bytes
        + b"\r\n"
    )


def get_today_overlay_counts(db: Session, target_date: date | None = None) -> dict[str, Any]:
    day = target_date or date.today()
    row = db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE lower(trim(result_status)) = 'ok') AS ok_count,
                COUNT(DISTINCT request_id) FILTER (WHERE lower(trim(result_status)) = 'ng') AS ng_count
            FROM public.vision_result
            WHERE created_at = :target_date
            """
        ),
        {"target_date": day},
    ).mappings().first()

    return {
        "date": day.isoformat(),
        "ok_count": int((row or {}).get("ok_count") or 0),
        "ng_count": int((row or {}).get("ng_count") or 0),
    }


def vision_status_placeholder() -> dict:
    return {
        "module": "vision",
        "message": "Vision realtime endpoints are enabled.",
        "default_mode": "onprem-overlay-ingest",
        "active_cameras": list_camera_states(),
        "pcb_model": get_pcb_model_status(),
    }
