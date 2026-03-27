"""운영용 LLM 모듈의 지식 베이스 로딩/인덱싱 헬퍼.

이 레이어는 파일 수집과 문서 파싱에 집중하고,
채팅 에이전트는 검색과 응답 생성에 더 집중할 수 있도록 분리한다.
"""

import os
import importlib
import base64
import shutil
import time
from pathlib import Path
from typing import List

try:
    from langchain_community.vectorstores import FAISS
except Exception:  # pragma: no cover - optional dependency
    FAISS = None

try:
    from langchain_core.documents import Document
except Exception:  # pragma: no cover - optional dependency
    Document = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except Exception:  # pragma: no cover - optional dependency
    RecursiveCharacterTextSplitter = None

from .agent_service import get_agent as _get_agent
from .openai_service import get_openai_client
from .security_utils import redact_exception, redact_text

DEFAULT_KNOWLEDGE_PATH = Path(__file__).resolve().parents[1] / "knowledge_base"
# `_knowledge_state`는 상태 조회 API에서 그대로 노출되므로
# 프런트나 상태 소비 쪽을 함께 바꾸지 않는 한 필드명을 쉽게 바꾸지 않는다.
_knowledge_state = {
    "fingerprint": None,
    "last_chunks": 0,
    "last_checked_at": 0.0,
    "vector_chunks": 0,
    "retriever_ready": False,
    "last_error": "",
    "docs_total": 0,
    "chunked_docs": 0,
    "image_ocr_success": 0,
    "image_ocr_failed": 0,
    "local_ocr_used": 0,
    "sidecar_ocr_used": 0,
}
_pdf_reader_class = None
_pdf_reader_checked = False
_image_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_local_ocr_probe = {"checked": False, "available": False, "reason": "", "cmd": ""}


def _read_response_text(response) -> str:
    """Responses API 응답에서 일반 텍스트만 추출한다."""
    text = str(getattr(response, "output_text", "") or "").strip()
    if text:
        return text
    for item in (getattr(response, "output", None) or []):
        for content in (getattr(item, "content", None) or []):
            if getattr(content, "type", "") == "output_text":
                candidate = str(getattr(content, "text", "") or "").strip()
                if candidate:
                    return candidate
    return ""


class _LiteDocument:
    """LangChain `Document`를 쓸 수 없을 때 사용하는 최소 대체 객체."""

    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


def _make_document(page_content: str, metadata: dict):
    if Document is not None:
        return Document(page_content=page_content, metadata=metadata)
    return _LiteDocument(page_content=page_content, metadata=metadata)


def get_agent():
    return _get_agent()


def get_knowledge_path() -> Path:
    configured = os.getenv("LLM_KNOWLEDGE_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_KNOWLEDGE_PATH


def list_knowledge_files() -> List[str]:
    knowledge_path = get_knowledge_path()
    knowledge_path.mkdir(parents=True, exist_ok=True)
    return sorted(path.name for path in knowledge_path.iterdir() if path.is_file())


def _knowledge_fingerprint() -> tuple:
    # 파일명, 수정 시각, 크기를 함께 기록해
    # 지식 폴더에 실제 변경이 없으면 비싼 OCR/벡터 작업을 건너뛴다.
    knowledge_path = get_knowledge_path()
    knowledge_path.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in sorted(knowledge_path.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        stat = path.stat()
        entries.append((path.name, stat.st_mtime_ns, stat.st_size))
    return tuple(entries)


def _load_text_document(path: Path):
    try:
        return [_make_document(page_content=path.read_text(encoding="utf-8"), metadata={"source": path.name})]
    except Exception as exc:
        print(f"[knowledge] text read failed: {path.name} ({redact_exception(exc)})")
        return []


def _get_pdf_reader_class():
    global _pdf_reader_class, _pdf_reader_checked
    if _pdf_reader_checked:
        return _pdf_reader_class

    candidates = [
        ("pypdf", "PdfReader"),
        ("PyPDF2", "PdfReader"),
    ]
    for module_name, class_name in candidates:
        try:
            module = importlib.import_module(module_name)
            reader_class = getattr(module, class_name, None)
            if reader_class is not None:
                _pdf_reader_class = reader_class
                _pdf_reader_checked = True
                print(f"[knowledge] pdf reader loaded: {module_name}.{class_name}")
                return _pdf_reader_class
        except Exception:
            continue

    _pdf_reader_checked = True
    _pdf_reader_class = None
    return None


def _load_pdf_document(path: Path):
    sidecar_text, sidecar_name = _read_sidecar_ocr_text(path)
    pdf_reader_class = _get_pdf_reader_class()
    if pdf_reader_class is None:
        if sidecar_text:
            print(f"[knowledge] pdf reader unavailable, using sidecar OCR text: {path.name} ({sidecar_name})")
            return [_make_document(page_content=sidecar_text, metadata={"source": path.name, "page": 1})]
        print(f"[knowledge] pdf reader unavailable (install pypdf or PyPDF2). skipped: {path.name}")
        return []

    try:
        reader = pdf_reader_class(str(path))
    except Exception as exc:
        if sidecar_text:
            print(f"[knowledge] pdf open failed, using sidecar OCR text: {path.name} ({sidecar_name})")
            return [_make_document(page_content=sidecar_text, metadata={"source": path.name, "page": 1})]
        print(f"[knowledge] pdf open failed: {path.name} ({redact_exception(exc)})")
        return []

    docs = []
    extracted_pages = 0
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:
            print(f"[knowledge] pdf page read failed: {path.name}#p{idx} ({redact_exception(exc)})")
            continue
        if text:
            extracted_pages += 1
            docs.append(_make_document(page_content=text, metadata={"source": path.name, "page": idx}))
    if extracted_pages == 0:
        if sidecar_text:
            print(f"[knowledge] pdf text extraction empty, using sidecar OCR text: {path.name} ({sidecar_name})")
            docs.append(_make_document(page_content=sidecar_text, metadata={"source": path.name, "page": 1}))
            return docs
        # 스캔 PDF는 텍스트 레이어가 없을 수 있으므로
        # 검색에서 파일이 완전히 누락되지 않도록 안내용 placeholder를 남긴다.
        placeholder = (
            f"document file: {path.name}\n"
            "pdf text extraction returned empty (likely scanned/image-based PDF).\n"
            "tip: run OCR and provide sidecar text file (*.txt or *_ocr.txt)."
        )
        docs.append(_make_document(page_content=placeholder, metadata={"source": path.name, "page": 0}))
        print(f"[knowledge] pdf text extraction empty: {path.name} (likely scanned/image-based PDF)")
    return docs


def _image_data_url(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(suffix, "application/octet-stream")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _read_sidecar_ocr_text(path: Path):
    # OCR 품질이 낮거나 문서에서 텍스트를 직접 추출할 수 없을 때를 대비해
    # 운영자가 붙여둔 sidecar 텍스트 파일을 보조 입력으로 사용한다.
    candidates = [
        path.with_suffix(".txt"),
        path.with_name(f"{path.stem}_ocr.txt"),
        path.with_name(f"{path.stem}.ocr.txt"),
    ]
    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            text = candidate.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        if text:
            return text, candidate.name
    return "", ""


def _resolve_tesseract_cmd() -> str:
    env_cmd = os.getenv("TESSERACT_CMD", "").strip() or os.getenv("TESSERACT_PATH", "").strip()
    if env_cmd:
        return env_cmd
    discovered = shutil.which("tesseract")
    if discovered:
        return discovered
    common_paths = [
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
    ]
    for candidate in common_paths:
        if Path(candidate).exists():
            return candidate
    return ""


def _probe_local_ocr() -> dict:
    if _local_ocr_probe.get("checked") and _local_ocr_probe.get("available"):
        return dict(_local_ocr_probe)

    result = {"checked": True, "available": False, "reason": "", "cmd": ""}
    try:
        import pytesseract
    except Exception:
        result["reason"] = "pytesseract_not_installed"
        _local_ocr_probe.update(result)
        return dict(_local_ocr_probe)

    cmd = _resolve_tesseract_cmd()
    result["cmd"] = cmd
    if not cmd:
        result["reason"] = "tesseract_not_found"
        _local_ocr_probe.update(result)
        return dict(_local_ocr_probe)

    try:
        if not os.getenv("TESSDATA_PREFIX", "").strip():
            cmd_path = Path(cmd)
            tessdata_candidates = [
                cmd_path.parent / "tessdata",
                cmd_path.parent.parent / "share" / "tessdata",
                cmd_path.parent.parent.parent / "share" / "tessdata",
            ]
            for candidate in tessdata_candidates:
                if candidate.exists() and candidate.is_dir():
                    os.environ["TESSDATA_PREFIX"] = str(candidate)
                    break
        pytesseract.pytesseract.tesseract_cmd = cmd
        _ = str(pytesseract.get_tesseract_version())
    except Exception:
        result["reason"] = "tesseract_unavailable"
        _local_ocr_probe.update(result)
        return dict(_local_ocr_probe)

    result["available"] = True
    _local_ocr_probe.update(result)
    return dict(_local_ocr_probe)


def _local_image_ocr_text(path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except Exception:
        return ""

    probe = _probe_local_ocr()
    if not probe.get("available"):
        return ""

    lang = os.getenv("LOCAL_OCR_LANG", "eng+kor").strip() or "eng+kor"
    try:
        with Image.open(path) as image:
            return str(pytesseract.image_to_string(image, lang=lang) or "").strip()
    except Exception as exc:
        print(f"[knowledge] local image OCR failed: {path.name} ({redact_exception(exc)})")
        return ""


def _load_image_document(path: Path, ingest_stats: dict):
    sidecar_text, sidecar_name = _read_sidecar_ocr_text(path)
    client, err = get_openai_client()
    if err:
        if sidecar_text:
            ingest_stats["sidecar_ocr_used"] = int(ingest_stats.get("sidecar_ocr_used", 0)) + 1
            return [_make_document(page_content=sidecar_text, metadata={"source": path.name, "page": 1})]
        local_text = _local_image_ocr_text(path)
        if local_text:
            ingest_stats["local_ocr_used"] = int(ingest_stats.get("local_ocr_used", 0)) + 1
            return [_make_document(page_content=local_text, metadata={"source": path.name, "page": 1})]
        ingest_stats["image_ocr_failed"] = int(ingest_stats.get("image_ocr_failed", 0)) + 1
        placeholder = (
            f"document file: {path.name}\n"
            f"image OCR unavailable: {redact_text(err)}\n"
            "tip: set OPENAI_API_KEY, install local OCR, or provide sidecar text file (*.txt or *_ocr.txt)."
        )
        return [_make_document(page_content=placeholder, metadata={"source": path.name, "page": 1})]

    model = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
    try:
        image_url = _image_data_url(path)
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract all visible text from this image exactly as written. "
                                "Keep original language and line breaks. "
                                "If no readable text exists, return NO_TEXT."
                            ),
                        },
                        {"type": "input_image", "image_url": image_url},
                    ],
                }
            ],
        )
        text = _read_response_text(response)
    except Exception as exc:
        print(f"[knowledge] image OCR failed: {path.name} ({redact_exception(exc)})")
        text = ""

    normalized = str(text or "").strip()
    if normalized and normalized.upper() != "NO_TEXT":
        ingest_stats["image_ocr_success"] = int(ingest_stats.get("image_ocr_success", 0)) + 1
        return [_make_document(page_content=normalized, metadata={"source": path.name, "page": 1})]

    local_text = _local_image_ocr_text(path)
    if local_text:
        ingest_stats["local_ocr_used"] = int(ingest_stats.get("local_ocr_used", 0)) + 1
        return [_make_document(page_content=local_text, metadata={"source": path.name, "page": 1})]

    if sidecar_text:
        ingest_stats["sidecar_ocr_used"] = int(ingest_stats.get("sidecar_ocr_used", 0)) + 1
        print(f"[knowledge] using sidecar OCR text for {path.name}: {sidecar_name}")
        return [_make_document(page_content=sidecar_text, metadata={"source": path.name, "page": 1})]

    ingest_stats["image_ocr_failed"] = int(ingest_stats.get("image_ocr_failed", 0)) + 1
    placeholder = (
        f"document file: {path.name}\n"
        "image OCR produced no text.\n"
        "tip: verify image quality or provide sidecar text file (*.txt or *_ocr.txt)."
    )
    return [_make_document(page_content=placeholder, metadata={"source": path.name, "page": 1})]


def update_knowledge() -> int:
    agent = get_agent()
    knowledge_path = get_knowledge_path()
    knowledge_path.mkdir(parents=True, exist_ok=True)

    ingest_stats = {
        "image_ocr_success": 0,
        "image_ocr_failed": 0,
        "local_ocr_used": 0,
        "sidecar_ocr_used": 0,
    }

    all_docs = []
    for path in knowledge_path.iterdir():
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        # 파일 타입별로 독립적으로 파싱해
        # 일부 의존성 문제로 전체 수집이 막히지 않도록 한다.
        if suffix == ".txt":
            all_docs.extend(_load_text_document(path))
        elif suffix == ".pdf":
            all_docs.extend(_load_pdf_document(path))
        elif suffix in _image_suffixes:
            all_docs.extend(_load_image_document(path, ingest_stats))

    chunked_docs = all_docs
    if RecursiveCharacterTextSplitter is not None and all_docs:
        try:
            # 검색 재현율을 높이기 위해 청크는 너무 크지 않게 유지하되,
            # 페이지 사이 문맥이 끊기지 않도록 적당한 overlap을 둔다.
            splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
            chunked_docs = splitter.split_documents(all_docs)
        except Exception as exc:
            print(f"[knowledge] local chunking failed: {redact_exception(exc)}")
            chunked_docs = all_docs

    local_chunks = []
    for doc in chunked_docs:
        content = (getattr(doc, "page_content", "") or "").strip()
        if not content:
            continue
        metadata = getattr(doc, "metadata", {}) or {}
        local_chunks.append(
            {
                "content": content,
                "source": str(metadata.get("source", "") or "").strip(),
                "page": metadata.get("page"),
            }
        )
    agent.set_local_knowledge_docs(local_chunks)

    # FAISS나 임베딩이 없어도 로컬 청크 기반 응답은 가능해야 하므로
    # 우선 폴백 검색 상태부터 갱신한다.
    _knowledge_state["fingerprint"] = _knowledge_fingerprint()
    _knowledge_state["last_chunks"] = len(local_chunks)
    _knowledge_state["last_checked_at"] = time.time()
    _knowledge_state["docs_total"] = len(all_docs)
    _knowledge_state["chunked_docs"] = len(chunked_docs)
    _knowledge_state["image_ocr_success"] = int(ingest_stats.get("image_ocr_success", 0))
    _knowledge_state["image_ocr_failed"] = int(ingest_stats.get("image_ocr_failed", 0))
    _knowledge_state["local_ocr_used"] = int(ingest_stats.get("local_ocr_used", 0))
    _knowledge_state["sidecar_ocr_used"] = int(ingest_stats.get("sidecar_ocr_used", 0))
    _knowledge_state["last_error"] = ""

    can_vectorize = all([FAISS, Document, RecursiveCharacterTextSplitter]) and chunked_docs and agent.embeddings
    if can_vectorize:
        try:
            vector_db = FAISS.from_documents(chunked_docs, agent.embeddings)
            agent.retriever = vector_db.as_retriever(search_kwargs={"k": 6})
            _knowledge_state["vector_chunks"] = len(chunked_docs)
            _knowledge_state["retriever_ready"] = True
            return len(local_chunks)
        except Exception as exc:
            safe_error = redact_exception(exc)
            print(f"[knowledge] indexing failed: {safe_error}")
            _knowledge_state["last_error"] = safe_error

    agent.retriever = None
    _knowledge_state["vector_chunks"] = 0
    _knowledge_state["retriever_ready"] = False

    if not _knowledge_state["last_error"]:
        # 상태 조회 시 폴백 이유를 바로 파악할 수 있도록
        # 빈 문서인지, 의존성 부족인지, 임베딩 문제인지 명시적으로 기록한다.
        if not chunked_docs:
            _knowledge_state["last_error"] = "no_documents_after_parsing"
        elif not all([FAISS, Document, RecursiveCharacterTextSplitter]):
            _knowledge_state["last_error"] = "vector_dependencies_unavailable"
        elif not agent.embeddings:
            _knowledge_state["last_error"] = "embeddings_unavailable"
        else:
            _knowledge_state["last_error"] = "vector_index_unavailable"

    return len(local_chunks)


def ensure_knowledge_current() -> int:
    # 짧은 시간 안의 연속 채팅은 직전 검사 결과를 재사용해
    # 매 요청마다 파일 시스템 전체를 다시 훑는 비용을 줄인다.
    last_checked_at = float(_knowledge_state.get("last_checked_at", 0.0) or 0.0)
    if last_checked_at and (time.time() - last_checked_at) < 3.0:
        return int(_knowledge_state["last_chunks"] or 0)
    fingerprint = _knowledge_fingerprint()
    _knowledge_state["last_checked_at"] = time.time()
    if _knowledge_state["fingerprint"] != fingerprint:
        return update_knowledge()
    return int(_knowledge_state["last_chunks"] or 0)


def reindex_knowledge() -> dict:
    files = list_knowledge_files()
    chunks = update_knowledge()
    retriever_ready = bool(_knowledge_state.get("retriever_ready"))
    has_local_chunks = int(_knowledge_state.get("last_chunks", 0) or 0) > 0
    local_ocr = _probe_local_ocr()
    return {
        "knowledge_path": str(get_knowledge_path()),
        "files": files,
        "indexed_chunks": int(chunks),
        "vector_indexed_chunks": int(_knowledge_state.get("vector_chunks", 0) or 0),
        "retriever_ready": retriever_ready,
        "chunking": {
            "parsed_docs": int(_knowledge_state.get("docs_total", 0) or 0),
            "chunked_docs": int(_knowledge_state.get("chunked_docs", 0) or 0),
        },
        "ocr": {
            "image_ocr_success": int(_knowledge_state.get("image_ocr_success", 0) or 0),
            "image_ocr_failed": int(_knowledge_state.get("image_ocr_failed", 0) or 0),
            "local_ocr_used": int(_knowledge_state.get("local_ocr_used", 0) or 0),
            "sidecar_ocr_used": int(_knowledge_state.get("sidecar_ocr_used", 0) or 0),
            "local_ocr_available": bool(local_ocr.get("available")),
            "local_ocr_reason": str(local_ocr.get("reason", "") or ""),
            "tesseract_cmd": str(local_ocr.get("cmd", "") or ""),
        },
        "last_error": str(_knowledge_state.get("last_error", "") or ""),
        "status": (
            "ok"
            if retriever_ready
            else "fallback_only_or_embedding_unavailable" if has_local_chunks else "empty_or_embedding_unavailable"
        ),
    }


def load_knowledge_on_startup() -> None:
    print("[startup] loading local knowledge base")
    update_knowledge()


def get_knowledge_status() -> dict:
    ensure_knowledge_current()
    local_ocr = _probe_local_ocr()
    return {
        "knowledge_path": str(get_knowledge_path()),
        "files": list_knowledge_files(),
        "indexed_chunks": int(_knowledge_state.get("last_chunks", 0) or 0),
        "vector_indexed_chunks": int(_knowledge_state.get("vector_chunks", 0) or 0),
        "retriever_ready": bool(_knowledge_state.get("retriever_ready")),
        "chunking": {
            "parsed_docs": int(_knowledge_state.get("docs_total", 0) or 0),
            "chunked_docs": int(_knowledge_state.get("chunked_docs", 0) or 0),
        },
        "ocr": {
            "image_ocr_success": int(_knowledge_state.get("image_ocr_success", 0) or 0),
            "image_ocr_failed": int(_knowledge_state.get("image_ocr_failed", 0) or 0),
            "local_ocr_used": int(_knowledge_state.get("local_ocr_used", 0) or 0),
            "sidecar_ocr_used": int(_knowledge_state.get("sidecar_ocr_used", 0) or 0),
            "local_ocr_available": bool(local_ocr.get("available")),
            "local_ocr_reason": str(local_ocr.get("reason", "") or ""),
            "tesseract_cmd": str(local_ocr.get("cmd", "") or ""),
        },
        "last_error": str(_knowledge_state.get("last_error", "") or ""),
        "status": "ok" if get_agent().retriever is not None else "fallback_only_or_embedding_unavailable",
    }
