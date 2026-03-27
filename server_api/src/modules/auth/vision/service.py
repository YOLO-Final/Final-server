"""Face ID 전처리/임베딩 추출 유틸.

API 계층에서는 이 모듈을 통해 base64 이미지를 디코딩하고,
InsightFace로 얼굴 검출 및 임베딩 추출을 수행한다.
"""

import base64
import re
from functools import lru_cache
from typing import Any


class FaceEngineUnavailableError(RuntimeError):
    pass


# 브라우저/모바일에서 올라오는 base64 이미지를 OpenCV 입력 이미지로 변환한다.
def _decode_base64_image(image_base64: str) -> Any:
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise FaceEngineUnavailableError("OpenCV or NumPy is not available in the API container.") from exc

    if not isinstance(image_base64, str) or not image_base64.strip():
        raise ValueError("Invalid base64 image payload.")

    payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
    payload = payload.strip()
    # 전송 중 섞일 수 있는 줄바꿈/공백을 제거한 뒤 디코딩한다.
    payload = re.sub(r"\s+", "", payload)

    def _decode_candidates(value: str) -> bytes | None:
        if not value:
            return None

        candidates = [value]
        # 프록시/클라이언트 변환 과정에서 URL-safe base64 형태가 섞일 수 있다.
        if "-" in value or "_" in value:
            candidates.append(value.replace("-", "+").replace("_", "/"))

        for item in candidates:
            # Base64 길이는 4의 배수여야 하므로 부족한 padding을 보완한다.
            padded = item + ("=" * ((4 - len(item) % 4) % 4))
            try:
                return base64.b64decode(padded, validate=True)
            except Exception:
                pass
            try:
                return base64.b64decode(padded, validate=False)
            except Exception:
                pass

        return None

    raw = _decode_candidates(payload)
    if raw is None:
        raise ValueError("Invalid base64 image payload.")

    image_array = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Failed to decode image data.")

    return image


@lru_cache(maxsize=1)
def _get_face_analyzer():
    try:
        import insightface  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise FaceEngineUnavailableError("InsightFace is not available in the API container.") from exc

    try:
        analyzer = insightface.app.FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        analyzer.prepare(ctx_id=-1, det_size=(640, 640))
        return analyzer
    except Exception as exc:  # noqa: BLE001
        raise FaceEngineUnavailableError("InsightFace initialization failed.") from exc


def detect_face(image_base64: str) -> bool:
    image = _decode_base64_image(image_base64)
    analyzer = _get_face_analyzer()
    faces = analyzer.get(image)
    return len(faces) > 0


# 여러 얼굴이 잡히면 가장 크게 보이는 얼굴을 대표 얼굴로 선택한다.
def extract_face_embedding(image_base64: str) -> list[float]:
    image = _decode_base64_image(image_base64)
    analyzer = _get_face_analyzer()
    faces = analyzer.get(image)

    if not faces:
        raise ValueError("Face not detected.")

    # 프레임 안에 얼굴이 여러 개면 가장 큰 얼굴을 기준으로 사용한다.
    target_face = max(
        faces,
        key=lambda face: (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]),
    )

    embedding = target_face.embedding
    return [float(value) for value in embedding]
