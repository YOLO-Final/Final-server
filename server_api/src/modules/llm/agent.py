"""운영용 LLM 라우트에서 사용하는 주 채팅/웹검색 에이전트.

대시보드 채팅의 전체 응답 경로를 이 파일이 담당한다.
대화 메모리 관리, 지식 검색, 웹 검색 보강, 프롬프트 구성,
최종 응답 스트리밍까지 모두 이 안에서 이어진다.
"""

import os
import json
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, List, Tuple
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv
try:
    from langchain_core.embeddings import Embeddings
except Exception:  # pragma: no cover - optional dependency
    Embeddings = object

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:  # pragma: no cover - optional dependency
    ChatGoogleGenerativeAI = None

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except Exception:  # pragma: no cover - optional dependency
    ChatOpenAI = None
    OpenAIEmbeddings = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None

RE_WHITESPACE = re.compile(r"\s+")
RE_SESSION_SAFE = re.compile(r"[^0-9A-Za-z._-]")
RE_LIST_LABEL_LINE = re.compile(r"(?im)^\s*(?:[-*]|\d+[.)])?\s*(?:summary|details|next steps?)\s*:?\s*$")
RE_MULTI_NEWLINES = re.compile(r"\n{3,}")
RE_TOKENIZE_KO_EN = re.compile(r"[0-9A-Za-z]{2,}|[\uac00-\ud7a3]{2,}")
RE_HAS_HANGUL = re.compile(r"[\uac00-\ud7a3]")
RE_YEAR = re.compile(r"(20\d{2})")
RE_FILENAME_CANDIDATE = re.compile(r"[0-9A-Za-z\uac00-\ud7a3][0-9A-Za-z\uac00-\ud7a3 _\-.]{0,120}\.[0-9A-Za-z]{1,8}")
RE_INLINE_URL = re.compile(r"https?://[^\s)\]>\"']+")
RE_INLINE_URL_ALT = re.compile(r"https?://[^\s)\]>]+")
RE_DATE_YMD_FLEX = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")

DATE_PARSE_FORMATS = (
    "%Y-%m-%d",
    "%Y.%m.%d",
    "%Y/%m/%d",
    "%Y-%m",
    "%Y.%m",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%Y%m%d",
)

TRUSTED_FRESH_DOMAINS = (
    "go.kr", "korea.kr", "gov", "apple.com", "support.apple.com", "samsung.com", "google.com",
    "store.google.com", "pixel.google", "oneplus.com", "xiaomi.com", "motorola.com", "sony.com",
    "oppo.com", "vivo.com", "asus.com", "nothing.tech", "newspim.com", "yonhapnews.co.kr",
    "nikkei.com", "thelec.kr", "digitimes.com", "reuters.com", "apnews.com", "bbc.com",
    "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "investing.com", "marketwatch.com",
    "yna.co.kr", "newsis.com", "kbs.co.kr", "sbs.co.kr", "chosun.com", "joongang.co.kr",
    "donga.com", "hankyung.com", "mk.co.kr",
)
OFFICIAL_PRODUCT_DOMAINS = (
    "apple.com", "support.apple.com", "samsung.com", "google.com", "store.google.com", "pixel.google",
    "oneplus.com", "xiaomi.com", "motorola.com", "sony.com", "oppo.com", "vivo.com", "asus.com",
    "nothing.tech",
)
LOW_SIGNAL_DOMAINS = (
    "youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com", "reddit.com", "x.com", "twitter.com",
)
OFFICIAL_PUBLIC_DOMAINS = (
    "go.kr", "korea.kr", "gov", "whitehouse.gov", "congress.gov", "senate.gov", "house.gov", "state.gov", "europa.eu", "gov.uk",
)

NOW_INTENT_TOKENS = (
    "현재", "지금", "오늘", "요즘", "최근", "최신", "근황", "업데이트",
    "current", "now", "today", "latest", "recent", "update",
)
BROAD_KNOWLEDGE_TOKENS = (
    "전체", "전부", "모든", "정리", "요약", "all", "full", "entire", "summary",
)
OCR_TEXT_ONLY_TOKENS = (
    "ocr", "raw text", "exact text", "verbatim", "text only", "only text", "image text", "extract text",
    "원문", "텍스트만", "문자만", "그대로", "있는 그대로", "이미지 글자", "이미지 텍스트", "이미지 내용", "추출된 텍스트", "ocr 텍스트",
)
FACTUAL_CUES = (
    "최신", "최근", "실시간", "업데이트", "뉴스", "기사", "발표", "일정", "결과", "점수", "주가", "가격", "환율", "통계", "데이터", "비교", "순위", "누구", "언제", "어디", "무엇",
    "news", "price", "stock", "weather", "schedule", "result", "rate", "data", "compare", "ranking", "who", "when", "where", "what", "president", "prime minister", "celebrity", "actor", "singer",
)


def _normalized_host(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _host_matches(host: str, domains: Tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)

def _load_agent_dotenv() -> None:
    base_dir = Path(__file__).resolve().parent
    project_root_dir = base_dir.parent.parent.parent.parent
    candidates = [
        base_dir / ".env",
        Path.cwd() / ".env",
        project_root_dir / ".env",
        base_dir / "sample" / ".env",
    ]

    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        # 이미 프로세스에 주입된 환경값은 유지하고,
        # 존재하는 `.env` 파일만 순서대로 보조적으로 읽어온다.
        load_dotenv(dotenv_path=candidate, override=False)


_load_agent_dotenv()


class _DirectOpenAIEmbeddings(Embeddings):
    """LangChain 임베딩이 없을 때 쓰는 최소 OpenAI 임베딩 어댑터."""

    def __init__(self, api_key: str, model: str):
        if OpenAI is None:
            raise RuntimeError("openai package is not available")
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=texts)
        return [list(item.embedding) for item in response.data]

    def embed_query(self, text: str) -> List[float]:
        response = self.client.embeddings.create(model=self.model, input=text or "")
        return list(response.data[0].embedding)


class CSAgent:
    """채팅, 지식 검색, 웹 검색을 함께 조율하는 상태 기반 오케스트레이터."""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "")
        self.serper_api_key = os.getenv("SERPER_API_KEY", "").strip()
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip()
        self.vllm_api_key = os.getenv("VLLM_API_KEY", "EMPTY")
        self.vllm_base_url = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8001/v1")

        self.openai_model = os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
        self.openai_web_model = os.getenv("OPENAI_WEB_MODEL", "gpt-4.1-mini")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.vllm_model = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        self.history_max_turns = int(os.getenv("HISTORY_MAX_TURNS", "8"))
        self.history_recent_turns = int(os.getenv("HISTORY_RECENT_TURNS", "4"))
        self.history_summary_chars = int(os.getenv("HISTORY_SUMMARY_CHARS", "1200"))
        self.web_cache_ttl_sec = int(os.getenv("WEB_CACHE_TTL_SEC", "180"))
        self.web_fresh_cache_ttl_sec = int(os.getenv("WEB_FRESH_CACHE_TTL_SEC", "45"))
        self.answer_cache_ttl_sec = int(os.getenv("ANSWER_CACHE_TTL_SEC", "90"))
        self.web_max_results = int(os.getenv("WEB_MAX_RESULTS", "6"))
        self.web_history_limit = int(os.getenv("WEB_HISTORY_LIMIT", "8"))
        self.openai_web_timeout_sec = float(os.getenv("OPENAI_WEB_TIMEOUT_SEC", "25"))
        self.openai_web_retries = int(os.getenv("OPENAI_WEB_RETRIES", "3"))
        self.web_retry_backoff_sec = float(os.getenv("WEB_RETRY_BACKOFF_SEC", "1.2"))
        self.web_fresh_source_mode = str(os.getenv("WEB_FRESH_SOURCE_MODE", "relaxed")).strip().lower()

        # 런타임 캐시는 프로세스 내부에만 유지해
        # 클라이언트 재생성이나 최근 검색 재계산 없이 빠르게 응답한다.
        self.retriever = None
        self.local_knowledge_docs: List[Dict[str, object]] = []
        self._llm_cache: Dict[str, object] = {}
        self._client_cache: Dict[str, object] = {}
        self._web_cache: OrderedDict[str, Dict[str, object]] = OrderedDict()
        self._answer_cache: OrderedDict[str, Dict[str, object]] = OrderedDict()
        self._session_state: Dict[str, Dict[str, object]] = {}
        self._state_lock = Lock()
        self._last_web_error = ""

        self.embeddings = self._init_embeddings()

    def _init_embeddings(self):
        if not self.openai_api_key:
            return None
        if OpenAIEmbeddings is not None:
            try:
                return OpenAIEmbeddings(
                    model=self.embedding_model,
                    openai_api_key=self.openai_api_key,
                    tiktoken_enabled=False,
                    check_embedding_ctx_length=False,
                )
            except Exception as exc:
                print(f"[agent] embedding init failed (langchain): {exc}")
        try:
            return _DirectOpenAIEmbeddings(api_key=self.openai_api_key, model=self.embedding_model)
        except Exception as exc:
            print(f"[agent] embedding init failed (direct): {exc}")
            return None

    def _session_key(self, session_id: str = "") -> str:
        normalized = RE_WHITESPACE.sub("-", (session_id or "").strip())
        normalized = RE_SESSION_SAFE.sub("", normalized)
        return normalized[:80] or "default"

    def _ensure_session_state(self, session_id: str = "") -> Dict[str, object]:
        key = self._session_key(session_id)
        with self._state_lock:
            if key not in self._session_state:
                # 같은 프로세스를 여러 사용자가 공유해도
                # 세션 간 대화 문맥이 섞이지 않도록 세션별 상태를 분리한다.
                self._session_state[key] = {
                    "chat_history": [],
                    "memory_summary": "",
                    "knowledge_memory": [],
                    "web_history": [],
                }
            return self._session_state[key]

    def _get_llm(self, provider: str):
        provider = (provider or "openai").lower()
        if provider in self._llm_cache:
            return self._llm_cache[provider]

        if provider in {"vllm", "vllm_fast"}:
            if ChatOpenAI is None:
                raise RuntimeError("langchain-openai is not available")
            llm = ChatOpenAI(
                model=self.vllm_model,
                openai_api_key=self.vllm_api_key,
                openai_api_base=self.vllm_base_url,
                temperature=0.1 if provider == "vllm_fast" else 0.3,
                streaming=True,
                max_retries=1 if provider == "vllm_fast" else 2,
                model_kwargs={"max_tokens": 512 if provider == "vllm_fast" else 1024},
            )
            self._llm_cache[provider] = llm
            return llm

        if provider == "gemini":
            if ChatGoogleGenerativeAI is None:
                raise RuntimeError("langchain-google-genai is not available")
            if not self.google_api_key:
                raise RuntimeError("GOOGLE_API_KEY is missing")
            llm = ChatGoogleGenerativeAI(
                model=self.gemini_model,
                google_api_key=self.google_api_key,
                temperature=0.3,
            )
            self._llm_cache[provider] = llm
            return llm

        provider = "openai"
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        if ChatOpenAI is None:
            return None

        llm = ChatOpenAI(
            model=self.openai_model,
            openai_api_key=self.openai_api_key,
            temperature=0.3,
            streaming=True,
            max_retries=2,
        )
        self._llm_cache[provider] = llm
        return llm

    def _get_openai_client(self, provider: str = "openai"):
        provider = (provider or "openai").lower()
        if provider in self._client_cache:
            return self._client_cache[provider]
        if OpenAI is None:
            raise RuntimeError("openai package is not available")

        if provider in {"vllm", "vllm_fast"}:
            client = OpenAI(api_key=self.vllm_api_key, base_url=self.vllm_base_url)
        else:
            if not self.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is missing")
            client = OpenAI(api_key=self.openai_api_key)

        self._client_cache[provider] = client
        return client

    def reset_memory(self, session_id: str = ""):
        key = self._session_key(session_id)
        with self._state_lock:
            self._session_state[key] = {
                "chat_history": [],
                "memory_summary": "",
                "knowledge_memory": [],
                "web_history": [],
            }

    def set_local_knowledge_docs(self, docs: List[Dict[str, object]]):
        with self._state_lock:
            self.local_knowledge_docs = docs or []

    def _one_line(self, text: str, max_chars: int = 180) -> str:
        normalized = RE_WHITESPACE.sub(" ", (text or "")).strip()
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 3].rstrip() + "..."

    def _remember(self, session_id: str, role: str, content: str):
        state = self._ensure_session_state(session_id)
        with self._state_lock:
            state["chat_history"].append({"role": role, "content": content})
            max_messages = self.history_max_turns * 2
            if len(state["chat_history"]) > max_messages:
                overflow = state["chat_history"][:-max_messages]
                state["chat_history"] = state["chat_history"][-max_messages:]
                if overflow:
                    # 오래된 대화는 요약으로 압축해
                    # 전체 흐름은 유지하면서도 프롬프트 길이를 제한한다.
                    state["memory_summary"] = self._merge_memory_summary(
                        str(state.get("memory_summary", "") or ""),
                        overflow,
                    )

    def _merge_memory_summary(self, current_summary: str, old_messages: List[Dict[str, str]]) -> str:
        pieces = [current_summary] if current_summary else []
        for item in old_messages:
            role = "User" if item.get("role") == "user" else "Assistant"
            text = self._one_line(item.get("content", ""))
            if text:
                pieces.append(f"{role}: {text}")
        merged = " | ".join(part for part in pieces if part).strip()
        if len(merged) > self.history_summary_chars:
            merged = merged[-self.history_summary_chars:]
        return merged

    def _history_block(self, session_id: str) -> str:
        state = self._ensure_session_state(session_id)
        with self._state_lock:
            chat_history = list(state.get("chat_history", []))
            memory_summary = str(state.get("memory_summary", "") or "")

        if not chat_history and not memory_summary:
            return "(No chat history)"

        lines = []
        if memory_summary:
            lines.append(f"[Earlier Summary] {memory_summary}")

        recent_messages = chat_history[-(self.history_recent_turns * 2) :]
        for item in recent_messages:
            role = "User" if item.get("role") == "user" else "Assistant"
            content = item.get("content", "") or ""
            if item.get("role") == "assistant":
                content = RE_LIST_LABEL_LINE.sub("", content)
                content = RE_MULTI_NEWLINES.sub("\n\n", content).strip()
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _tokenize_korean_english(self, text: str) -> set:
        tokens = RE_TOKENIZE_KO_EN.findall((text or "").lower())
        return set(tokens)

    def _normalize_knowledge_query(self, text_query: str) -> str:
        normalized = RE_WHITESPACE.sub(" ", (text_query or "")).strip().lower()
        normalized = re.sub(r"\bpcd\b", "pcb", normalized, flags=re.IGNORECASE)
        normalized = normalized.replace("피시디", "pcb")
        return normalized

    def _is_company_query_safe(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        keywords = [
            "\ud68c\uc0ac",
            "\ud68c\uc0ac\uba85",
            "\uc5c5\uccb4",
            "\uc81c\uc870\uc0ac",
            "\uba54\uc774\ucee4",
            "maker",
            "company",
            "vendor",
            "supplier",
        ]
        return any(keyword in query for keyword in keywords)

    def _direct_company_answer(self, text_query: str) -> str:
        if not self._is_company_query_safe(text_query):
            return ""
        patterns = [
            r"(?im)^\s*maker\s*:\s*(.+?)\s*$",
            r"(?im)^\s*company\s*:\s*(.+?)\s*$",
            r"(?im)^\s*(?:\ud68c\uc0ac\uba85|\ud68c\uc0ac|\uc5c5\uccb4|\uc81c\uc870\uc0ac)\s*:\s*(.+?)\s*$",
        ]
        company_name = ""
        for item in self.local_knowledge_docs:
            content = str(item.get("content", "") or "").strip()
            if not content:
                continue
            for pattern in patterns:
                match = re.search(pattern, content)
                if not match:
                    continue
                company_name = self._normalize_extracted_value(match.group(1).strip())
                if company_name:
                    break
            if company_name:
                break

        if not company_name:
            return ""

        board_name = ""
        board_matchers = [
            r"(?im)^\s*board\s*(?:type|종류)?\s*:\s*(.+?)\s*$",
            r"(?im)^\s*(?:board\s*종류|보드\s*종류|기판\s*종류)\s*:\s*(.+?)\s*$",
        ]
        for item in self.local_knowledge_docs:
            content = str(item.get("content", "") or "").strip()
            if not content:
                continue
            for pattern in board_matchers:
                match = re.search(pattern, content)
                if not match:
                    continue
                board_name = self._normalize_extracted_value(match.group(1).strip())
                if board_name:
                    break
            if board_name:
                break

        defect_keywords = []
        candidates = [
            "Mouse bite",
            "Spur",
            "Short",
            "Open",
            "Missing hole",
            "Spurious copper",
        ]
        merged_text = "\n".join(str(item.get("content", "") or "") for item in self.local_knowledge_docs)
        for candidate in candidates:
            if re.search(re.escape(candidate), merged_text, flags=re.IGNORECASE):
                defect_keywords.append(candidate)

        return (
            f"{company_name}는 키오스크 및 산업용 전자기기의 핵심 부품인 메인 PCB(Board) 설계, 제조, 품질 관리를 전문으로 하는 기업입니다.\n"
            "특히 키오스크 메인 PCB 개발 및 품질 안정화 기술을 기반으로 다양한 전자 시스템에 적용 가능한 고품질 PCB 솔루션을 제공하고 있습니다.\n\n"
            "회사는 PCB 제조 과정에서 발생할 수 있는 불량 유형을 체계적으로 분류하고 원인을 분석하여 신속한 개선 조치를 수행하는 품질 관리 시스템을 구축하고 있습니다. "
            "이를 통해 제품의 안정성과 신뢰성을 지속적으로 향상시키고 있습니다."
        )

    def _extract_target_years(self, text: str) -> List[int]:
        return [int(year) for year in RE_YEAR.findall(text or "")]

    def _has_now_intent(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        return any(token in query for token in NOW_INTENT_TOKENS)

    def _is_broad_knowledge_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        return any(keyword in query for keyword in BROAD_KNOWLEDGE_TOKENS)

    def _is_company_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        company_keywords = [
            "회사명",
            "회사",
            "업체",
            "제조사",
            "메이커",
            "maker",
            "vendor",
            "supplier",
            "corp",
        ]
        return any(keyword in query for keyword in company_keywords)

    def _is_public_office_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        office_keywords = [
            "대통령",
            "총리",
            "국가원수",
            "president",
            "prime minister",
            "head of state",
            "chancellor",
            "king",
            "queen",
        ]
        return any(keyword in query for keyword in office_keywords)

    def _is_celebrity_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        celebrity_keywords = [
            "\uc5f0\uc608\uc778",
            "\ubc30\uc6b0",
            "\uac00\uc218",
            "\uc544\uc774\ub3cc",
            "\uc140\ub7fd",
            "celebrity",
            "actor",
            "actress",
            "singer",
            "idol",
            "entertainment",
        ]
        return any(keyword in query for keyword in celebrity_keywords)

    def _is_public_figure_query(self, text_query: str) -> bool:
        return self._is_public_office_query(text_query) or self._is_celebrity_query(text_query)

    def _country_hint(self, text_query: str) -> str:
        query = (text_query or "").lower()
        country_tokens = [
            "대한민국",
            "한국",
            "south korea",
            "korea",
            "미국",
            "usa",
            "united states",
            "일본",
            "japan",
            "중국",
            "china",
            "영국",
            "uk",
            "united kingdom",
            "프랑스",
            "france",
            "독일",
            "germany",
        ]
        if any(token in query for token in country_tokens):
            return ""
        if "대통령" in query or "총리" in query:
            return "대한민국 South Korea"
        return ""

    def _is_news_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        news_tokens = [
            "뉴스",
            "기사",
            "보도",
            "헤드라인",
            "속보",
            "발표",
            "news",
            "article",
            "headline",
            "report",
            "press release",
        ]
        return any(token in query for token in news_tokens)

    def _prefer_news_results(self, text_query: str, fresh_required: bool) -> bool:
        if not fresh_required:
            return False
        return self._is_news_query(text_query)

    def _official_product_hint(self, text_query: str) -> str:
        query = (text_query or "").lower()
        if "iphone" in query or "아이폰" in query or "ipad" in query or "맥북" in query or "macbook" in query:
            return "Apple official site"
        if "galaxy" in query or "갤럭시" in query:
            return "Samsung official site"
        if "pixel" in query or "픽셀" in query:
            return "Google official site"
        return "official site"

    def _is_latest_product_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        latest_tokens = [
            "현재",
            "지금",
            "오늘",
            "최신",
            "요즘",
            "current",
            "latest",
            "today",
            "newest",
        ]
        product_tokens = [
            "아이폰",
            "iphone",
            "갤럭시",
            "galaxy",
            "픽셀",
            "pixel",
            "ipad",
            "맥북",
            "macbook",
            "애플워치",
            "apple watch",
            "스마트폰",
            "휴대폰",
            "폰",
            "모델",
            "model",
            "기종",
            "라인업",
            "사양",
            "spec",
            "specs",
            "version",
        ]
        asks_latest = any(token in query for token in latest_tokens)
        asks_product = any(token in query for token in product_tokens)
        return asks_latest and asks_product

    def _fallback_knowledge_search(self, text_query: str) -> List[str]:
        query_tokens = self._tokenize_korean_english(text_query)
        if not query_tokens:
            return []

        company_query = self._is_company_query(text_query)
        scored = []
        for item in self.local_knowledge_docs:
            content = str(item.get("content", "") or "").strip()
            if not content:
                continue

            content_lower = content.lower()
            content_tokens = set(self._tokenize_korean_english(content))
            source = str(item.get("source", "") or "").strip().lower()
            source_tokens = set(self._tokenize_korean_english(source.replace(".", " ")))
            overlap = len(query_tokens & content_tokens)
            source_overlap = len(query_tokens & source_tokens)

            company_term_bonus = 0
            if company_query and any(
                term in content_lower for term in {"maker", "\ud68c\uc0ac", "\ud68c\uc0ac\uba85", "\uc5c5\uccb4", "\uc81c\uc870\uc0ac", "\uc8fc\uc2dd\ud68c\uc0ac"}
            ):
                company_term_bonus += 6

            if overlap <= 0 and source_overlap <= 0 and company_term_bonus <= 0:
                continue

            phrase_bonus = 2 if (text_query or "").strip().lower() in content_lower else 0
            pcb_boost = 3 if "pcb" in query_tokens and "pcb" in (content_lower + " " + source) else 0
            defect_boost = 2 if any(token in query_tokens for token in {"defect", "\ubd88\ub7c9", "\uc6d0\uc778", "\uc870\uce58"}) else 0
            score = overlap + (source_overlap * 2) + phrase_bonus + pcb_boost + defect_boost + company_term_bonus
            scored.append((score, item))

        if not scored and self.local_knowledge_docs and company_query:
            for item in self.local_knowledge_docs:
                content = str(item.get("content", "") or "").strip().lower()
                if any(term in content for term in {"maker", "\ud68c\uc0ac", "\uc8fc\uc2dd\ud68c\uc0ac"}):
                    scored.append((1, item))
                    break

        scored.sort(key=lambda pair: pair[0], reverse=True)
        max_snippets = 6 if self._is_broad_knowledge_query(text_query) else 4
        max_chars = 1600 if self._is_broad_knowledge_query(text_query) else 900
        snippets = []
        for _, item in scored[:max_snippets]:
            source = str(item.get("source", "") or "").strip()
            page = item.get("page")
            label = source
            if page is not None:
                label = f"{source}#p{page}" if source else f"p{page}"
            content = str(item.get("content", "") or "").strip()
            if len(content) > max_chars:
                content = content[:max_chars].rstrip() + "..."
            snippets.append(f"[{label}]\n{content}" if label else content)
        return snippets

    def _remember_knowledge(self, session_id: str, query: str, context: str):
        if not context:
            return
        state = self._ensure_session_state(session_id)
        normalized_query = self._one_line(query, max_chars=140)
        normalized_context = RE_WHITESPACE.sub(" ", context).strip()
        if len(normalized_context) > 900:
            normalized_context = normalized_context[:900].rstrip() + "..."

        with self._state_lock:
            state["knowledge_memory"].append({"query": normalized_query, "context": normalized_context})
            state["knowledge_memory"] = state["knowledge_memory"][-4:]

    def _knowledge_memory_block(self, session_id: str) -> str:
        state = self._ensure_session_state(session_id)
        with self._state_lock:
            knowledge_memory = list(state.get("knowledge_memory", []))

        if not knowledge_memory:
            return ""

        lines = []
        for item in knowledge_memory[-4:]:
            query = str(item.get("query", "") or "").strip()
            context = str(item.get("context", "") or "").strip()
            if context:
                lines.append(f"Q: {query}\nA-context: {context}" if query else context)

        merged = "\n\n".join(lines).strip()
        if len(merged) > 3000:
            merged = merged[-3000:]
        return merged

    def _doc_key(self, source: str, page: object, content: str) -> str:
        normalized_source = str(source or "").strip().lower()
        normalized_page = "" if page is None else str(page).strip()
        normalized_content = RE_WHITESPACE.sub(" ", (content or "")).strip().lower()
        return f"{normalized_source}|{normalized_page}|{normalized_content[:220]}"

    def _dense_retrieval_candidates(self, retrieval_queries: List[str], per_query_k: int) -> Dict[str, Dict[str, object]]:
        candidates: Dict[str, Dict[str, object]] = {}
        if not self.retriever:
            return candidates

        capped_k = max(1, int(per_query_k))
        for query_idx, retrieval_query in enumerate(retrieval_queries):
            try:
                docs = self.retriever.invoke(retrieval_query) or []
            except Exception as exc:
                print(f"[agent] retriever failed: {exc}")
                continue

            for rank, doc in enumerate(docs[:capped_k]):
                content = (getattr(doc, "page_content", "") or "").strip()
                if not content:
                    continue
                meta = getattr(doc, "metadata", {}) or {}
                source = str(meta.get("source", "") or "").strip()
                page = meta.get("page")
                key = self._doc_key(source, page, content)

                rank_score = float(capped_k - rank) / float(capped_k)
                query_bonus = 0.08 if query_idx == 0 else 0.0
                dense_score = rank_score + query_bonus

                previous = candidates.get(key)
                if previous is None or float(previous.get("dense_score", 0.0)) < dense_score:
                    candidates[key] = {
                        "key": key,
                        "source": source,
                        "page": page,
                        "content": content,
                        "dense_score": dense_score,
                    }
        return candidates

    def _sparse_retrieval_candidates(self, retrieval_queries: List[str], max_candidates: int) -> Dict[str, Dict[str, object]]:
        candidates: Dict[str, Dict[str, object]] = {}
        if not self.local_knowledge_docs:
            return candidates

        capped_max = max(1, int(max_candidates))
        for query_idx, retrieval_query in enumerate(retrieval_queries):
            query_tokens = self._tokenize_korean_english(retrieval_query)
            if not query_tokens:
                continue
            normalized_phrase = RE_WHITESPACE.sub(" ", (retrieval_query or "")).strip().lower()

            for item in self.local_knowledge_docs:
                content = str(item.get("content", "") or "").strip()
                if not content:
                    continue

                source = str(item.get("source", "") or "").strip()
                page = item.get("page")
                content_lower = content.lower()
                content_tokens = set(self._tokenize_korean_english(content))
                source_tokens = set(self._tokenize_korean_english(source.lower().replace(".", " ")))

                overlap = len(query_tokens & content_tokens)
                source_overlap = len(query_tokens & source_tokens)
                if overlap <= 0 and source_overlap <= 0:
                    continue

                phrase_bonus = 2.0 if normalized_phrase and normalized_phrase in content_lower else 0.0
                sparse_score = (float(overlap) + (float(source_overlap) * 1.8) + phrase_bonus) * (1.0 if query_idx == 0 else 0.9)
                key = self._doc_key(source, page, content)

                previous = candidates.get(key)
                if previous is None or float(previous.get("sparse_score", 0.0)) < sparse_score:
                    candidates[key] = {
                        "key": key,
                        "source": source,
                        "page": page,
                        "content": content,
                        "sparse_score": sparse_score,
                    }

        ordered = sorted(candidates.values(), key=lambda x: float(x.get("sparse_score", 0.0)), reverse=True)[:capped_max]
        return {str(item.get("key", "")): item for item in ordered if item.get("key")}

    def _knowledge_context(self, session_id: str, text_query: str) -> str:
        normalized_query = self._normalize_knowledge_query(text_query)
        retrieval_queries = [text_query]
        if normalized_query and normalized_query != (text_query or "").strip().lower():
            retrieval_queries.append(normalized_query)

        snippets: List[str] = []
        max_docs = 6 if self._is_broad_knowledge_query(text_query) else 4
        merged_candidates: Dict[str, Dict[str, object]] = {}

        dense_candidates = self._dense_retrieval_candidates(retrieval_queries, per_query_k=max_docs * 2)
        sparse_candidates = self._sparse_retrieval_candidates(retrieval_queries, max_candidates=max_docs * 4)

        # 벡터 검색 결과와 토큰 겹침 기반 결과를 함께 섞어
        # 용어가 흔들리거나 축약되거나 OCR 품질이 낮아도 검색이 버티게 한다.
        for key, candidate in dense_candidates.items():
            merged_candidates[key] = {
                "source": candidate.get("source", ""),
                "page": candidate.get("page"),
                "content": candidate.get("content", ""),
                "dense_score": float(candidate.get("dense_score", 0.0)),
                "sparse_score": 0.0,
            }

        for key, candidate in sparse_candidates.items():
            if key not in merged_candidates:
                merged_candidates[key] = {
                    "source": candidate.get("source", ""),
                    "page": candidate.get("page"),
                    "content": candidate.get("content", ""),
                    "dense_score": 0.0,
                    "sparse_score": float(candidate.get("sparse_score", 0.0)),
                }
            else:
                merged_candidates[key]["sparse_score"] = max(
                    float(merged_candidates[key].get("sparse_score", 0.0)),
                    float(candidate.get("sparse_score", 0.0)),
                )

        if merged_candidates:
            dense_weight = 1.0
            sparse_weight = 0.65
            ranked = sorted(
                merged_candidates.values(),
                key=lambda item: (dense_weight * float(item.get("dense_score", 0.0)))
                + (sparse_weight * float(item.get("sparse_score", 0.0))),
                reverse=True,
            )
            max_chars = 1600 if self._is_broad_knowledge_query(text_query) else 900

            for item in ranked[:max_docs]:
                source = str(item.get("source", "") or "").strip()
                page = item.get("page")
                label = f"{source}#p{page}" if source and page is not None else source or (f"p{page}" if page else "")
                content = str(item.get("content", "") or "").strip()
                if len(content) > max_chars:
                    content = content[:max_chars].rstrip() + "..."
                snippet_text = f"[{label}]\n{content}" if label else content
                if snippet_text and snippet_text not in snippets:
                    snippets.append(snippet_text)

        if len(snippets) < 2 and self.local_knowledge_docs:
            for retrieval_query in retrieval_queries:
                for snippet in self._fallback_knowledge_search(retrieval_query):
                    if snippet not in snippets:
                        snippets.append(snippet)
                    if len(snippets) >= max_docs:
                        break
                if len(snippets) >= max_docs:
                    break

        retrieved_context = "\n\n".join(snippets[:max_docs]).strip()
        if retrieved_context:
            self._remember_knowledge(session_id, text_query, retrieved_context)

        memory_context = self._knowledge_memory_block(session_id)
        if retrieved_context and memory_context:
            return f"{retrieved_context}\n\n[Recent Knowledge Memory]\n{memory_context}"
        return retrieved_context or memory_context

    def _normalize_extracted_value(self, value: str) -> str:
        normalized = RE_WHITESPACE.sub(" ", (value or "")).strip()
        replacements = {
            "주식회시": "주식회사",
        }
        for before, after in replacements.items():
            normalized = normalized.replace(before, after)
        return normalized

    def _normalize_filename_text(self, text: str) -> str:
        normalized = RE_WHITESPACE.sub(" ", (text or "")).strip().lower()
        normalized = normalized.strip("\"'`[](){}")
        normalized = normalized.replace("\\", "/")
        return normalized.split("/")[-1]

    def _filename_query_candidates(self, text_query: str) -> List[str]:
        query = self._normalize_filename_text(text_query)
        if not query:
            return []

        candidates = set()
        for match in RE_FILENAME_CANDIDATE.findall(query):
            item = self._normalize_filename_text(match)
            if item:
                candidates.add(item)

        if len(query) <= 120 and "." in query:
            candidates.add(query)

        return sorted(candidates, key=len, reverse=True)

    def _is_image_source(self, source: str) -> bool:
        suffix = Path(str(source or "").strip()).suffix.lower()
        return suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

    def _wants_ocr_text_only(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        return any(keyword in query for keyword in OCR_TEXT_ONLY_TOKENS)

    def _direct_ocr_text_answer(self, text_query: str) -> str:
        image_docs = [item for item in self.local_knowledge_docs if self._is_image_source(str(item.get("source", "")))]
        if not image_docs:
            return ""

        wants_text_only = self._wants_ocr_text_only(text_query)
        filename_candidates = self._filename_query_candidates(text_query)

        if not wants_text_only and not filename_candidates:
            return ""

        grouped: Dict[str, List[Dict[str, object]]] = {}
        for item in image_docs:
            source = str(item.get("source", "") or "").strip()
            if not source:
                continue
            grouped.setdefault(source, []).append(item)

        best_source = ""
        best_score = 0.0
        for source, items in grouped.items():
            source_name = self._normalize_filename_text(source)
            score = 0.0

            for candidate in filename_candidates:
                candidate_name = self._normalize_filename_text(candidate)
                if candidate_name == source_name:
                    score = max(score, 10.0)
                elif candidate_name and (candidate_name in source_name or source_name in candidate_name):
                    score = max(score, 6.0)

            if wants_text_only and len(grouped) == 1:
                score = max(score, 3.0)

            merged_content = "\n".join(str(item.get("content", "") or "") for item in items).lower()
            if wants_text_only and any(token in merged_content for token in self._tokenize_korean_english(text_query)):
                score += 1.0

            if score > best_score:
                best_score = score
                best_source = source

        if not best_source:
            return ""

        selected = grouped.get(best_source, [])
        if not selected:
            return ""

        # 사용자가 OCR 원문만 달라고 한 경우에는
        # 메인 LLM 요약을 거치지 않고 추출 텍스트를 그대로 돌려준다.
        selected = sorted(selected, key=lambda item: int(item.get("page") or 0))
        parts: List[str] = []
        seen = set()
        for item in selected:
            content = str(item.get("content", "") or "").strip()
            if not content:
                continue
            normalized = RE_WHITESPACE.sub(" ", content).strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            parts.append(content)

        return "\n\n".join(parts).strip()

    def _extract_knowledge_field(self, field_patterns: List[str]) -> str:
        for item in self.local_knowledge_docs:
            content = str(item.get("content", "") or "").strip()
            if not content:
                continue
            for pattern in field_patterns:
                match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
                if not match:
                    continue
                value = self._normalize_extracted_value(match.group(1).strip().splitlines()[0])
                if value:
                    return value
        return ""

    def _is_board_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        return any(keyword in query for keyword in ["board", "보드", "기판", "pcb 종류", "board 종류"])

    def _direct_knowledge_answer(self, text_query: str) -> str:
        if self._is_company_query(text_query):
            company_name = self._extract_knowledge_field(
                [
                    r"\bmaker\s*:\s*(.+)",
                    r"(?:회사명|업체명|제조사)\s*:\s*(.+)",
                ]
            )
            if company_name:
                return f"당신의 회사명은 {company_name}입니다."

        if self._is_board_query(text_query):
            board_name = self._extract_knowledge_field(
                [
                    r"board\s*종류\s*:\s*(.+)",
                    r"(?:보드\s*종류|기판\s*종류)\s*:\s*(.+)",
                ]
            )
            if board_name:
                return f"문서 기준 보드 종류는 {board_name}입니다."

        return ""

    def _normalize_search_query(self, text_query: str) -> str:
        query = RE_WHITESPACE.sub(" ", (text_query or "")).strip().lower()
        query = re.sub(r"[\"'`]+", "", query)
        return query[:200]

    def _normalize_response_language(self, language: str) -> str:
        return "en" if str(language or "").lower().startswith("en") else "ko"

    def _resolve_response_language(self, requested_language: str, text_query: str) -> str:
        """요청 언어와 질문 텍스트를 함께 보고 최종 응답 언어를 정한다."""
        normalized = self._normalize_response_language(requested_language)
        query = str(text_query or "")
        lowered = query.lower()
        asks_english = any(token in lowered for token in ("영어로", "english", "in english"))

        # 프런트 설정이 영문으로 남아 있어도, 한글 질문은 기본적으로 한글로 답한다.
        if RE_HAS_HANGUL.search(query) and not asks_english:
            return "ko"
        return normalized

    def _cache_key(self, normalized_query: str, fresh_required: bool, response_language: str = "ko") -> str:
        if not normalized_query:
            return ""
        normalized_language = self._normalize_response_language(response_language)
        return f"{normalized_query}|fresh={int(fresh_required)}|lang={normalized_language}"

    def _get_cached_web(self, normalized_query: str, fresh_required: bool, response_language: str = "ko") -> str:
        if not normalized_query:
            return ""
        cache_key = self._cache_key(normalized_query, fresh_required, response_language)
        entry = self._web_cache.get(cache_key)
        if not entry:
            return ""

        cached_at = float(entry.get("at", 0.0))
        ttl = self.web_fresh_cache_ttl_sec if fresh_required else self.web_cache_ttl_sec
        if (time.time() - cached_at) > ttl:
            self._web_cache.pop(cache_key, None)
            return ""
        # 캐시된 웹 컨텍스트에는 출처 블록까지 포함된 상태다.
        return str(entry.get("value", "") or "")

    def _set_cached_web(
        self,
        normalized_query: str,
        value: str,
        fresh_required: bool,
        response_language: str = "ko",
    ):
        if not normalized_query:
            return
        cache_key = self._cache_key(normalized_query, fresh_required, response_language)
        if cache_key in self._web_cache:
            self._web_cache.pop(cache_key, None)
        self._web_cache[cache_key] = {"value": value, "at": time.time()}
        if len(self._web_cache) > 80:
            self._web_cache.popitem(last=False)

    def _get_cached_answer(self, normalized_query: str, response_language: str = "ko") -> Tuple[str, List[str]]:
        if not normalized_query:
            return "", []
        cache_key = f"{normalized_query}|lang={self._normalize_response_language(response_language)}"
        entry = self._answer_cache.get(cache_key)
        if not entry:
            return "", []
        cached_at = float(entry.get("at", 0.0))
        if (time.time() - cached_at) > self.answer_cache_ttl_sec:
            self._answer_cache.pop(cache_key, None)
            return "", []
        answer = str(entry.get("answer", "") or "")
        links = [str(link) for link in (entry.get("links", []) or []) if link]
        return answer, links

    def _set_cached_answer(
        self,
        normalized_query: str,
        answer: str,
        links: List[str],
        response_language: str = "ko",
    ):
        if not normalized_query or not answer:
            return
        cache_key = f"{normalized_query}|lang={self._normalize_response_language(response_language)}"
        if cache_key in self._answer_cache:
            self._answer_cache.pop(cache_key, None)
        self._answer_cache[cache_key] = {
            "answer": answer,
            "links": links[: self.web_max_results],
            "at": time.time(),
        }
        if len(self._answer_cache) > 80:
            self._answer_cache.popitem(last=False)

    def _remember_direct_answer(self, session_id: str, text_query: str, answer: str) -> None:
        """우회 응답도 일반 LLM 응답처럼 메모리에 남기기 위한 헬퍼."""
        self._remember(session_id, "user", text_query)
        self._remember(session_id, "assistant", answer)

    def _compose_answer_with_sources(
        self,
        answer: str,
        links: List[str],
        max_links: int | None = None,
    ) -> str:
        text = self._sanitize_response_text(answer or "").strip()
        if not text:
            return ""
        lowered = text.lower()
        if (
            lowered.startswith("strict_fresh_public_office:")
            or "minimum official source links were not satisfied" in lowered
        ):
            return ""
        selected_links = links if max_links is None else links[:max(0, max_links)]
        if selected_links and "[Sources]" not in text:
            return f"{text}{self._format_citation_block(selected_links)}"
        return text

    def _store_web_context_result(
        self,
        normalized_query: str,
        session_id: str,
        text_query: str,
        search_query: str,
        context: str,
        fresh_required: bool,
        response_language: str,
        links: List[str] | None = None,
        source_count: int | None = None,
        max_links: int | None = None,
    ) -> str:
        """완성된 웹 컨텍스트를 캐시와 세션 메모리에 한 번에 반영한다."""
        final_context = self._compose_answer_with_sources(context, links or [], max_links=max_links)
        if not final_context:
            return ""
        remembered_sources = source_count if source_count is not None else len(links or [])
        self._set_cached_web(normalized_query, final_context, fresh_required, response_language)
        self._remember_web_context(
            session_id,
            text_query,
            search_query,
            final_context,
            fresh_required,
            remembered_sources,
        )
        return final_context

    def _build_web_query(self, text_query: str, fresh_required: bool) -> str:
        query = RE_WHITESPACE.sub(" ", (text_query or "")).strip()
        if self._is_public_figure_query(query):
            figure_tokens = [
                datetime.now().strftime("%Y-%m-%d"),
                "today",
                "latest",
                "current",
                "verified news",
            ]
            return f"{query} {' '.join(figure_tokens)}".strip()
        if self._is_public_office_query(query):
            hint = self._country_hint(query)
            office_tokens = [
                datetime.now().strftime("%Y-%m-%d"),
                "today",
                "current officeholder",
                "official source",
            ]
            suffix = " ".join(office_tokens)
            if hint:
                return f"{query} {hint} {suffix}".strip()
            return f"{query} {suffix}".strip()
        if self._is_latest_product_query(query):
            current = datetime.now()
            suffix = " ".join(
                [
                    current.strftime("%Y-%m-%d"),
                    "latest",
                    "current",
                    "official",
                    "product lineup",
                    "model",
                    "specs",
                    self._official_product_hint(query),
                ]
            )
            return f"{query} {suffix}".strip()
        if not fresh_required:
            return query

        current = datetime.now()
        current_tokens = [
            str(current.year),
            current.strftime("%B"),
            current.strftime("%Y-%m"),
            current.strftime("%Y-%m-%d"),
            "today",
            "latest",
            "current",
        ]
        if RE_YEAR.search(query):
            current_tokens = [current.strftime("%Y-%m-%d"), "today", "latest", "current"]
        return f"{query} {' '.join(current_tokens)}".strip()

    def _build_overview_query(self, text_query: str) -> str:
        query = RE_WHITESPACE.sub(" ", (text_query or "")).strip()
        if not query:
            return ""
        overview = re.sub(
            r"\b(today|latest|current|recent|news|article|headline|report|press\s+release|now)\b",
            " ",
            query,
            flags=re.IGNORECASE,
        )
        overview = re.sub(r"(오늘|최신|현재|최근|뉴스|기사|헤드라인|보도|속보)", " ", overview)
        overview = RE_WHITESPACE.sub(" ", overview).strip(" ,.-")
        return overview or query

    def _format_web_items(
        self,
        items: List[Dict[str, str]],
        seen_links: set,
        target_years: List[int] | None = None,
        fresh_required: bool = False,
        latest_product_query: bool = False,
    ) -> List[str]:
        now_dt = datetime.now()

        def _parse_date_value(raw: str):
            text = str(raw or "").strip()
            if not text:
                return None
            for fmt in DATE_PARSE_FORMATS:
                try:
                    return datetime.strptime(text[: len(now_dt.strftime(fmt))], fmt)
                except Exception:
                    continue
            match = RE_DATE_YMD_FLEX.search(text)
            if match:
                try:
                    return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                except Exception:
                    return None
            return None

        def _freshness_sort_key(item: Dict[str, str]):
            published_raw = str(item.get("date", "") or "")
            published_dt = _parse_date_value(published_raw)
            href = str(item.get("url") or item.get("href") or "").strip()
            trusted_bonus = 1 if href and self._is_trusted_fresh_source(href) else 0
            official_bonus = 2 if href and self._is_official_product_source(href) else 0
            recent_bonus = 0
            if published_dt is not None:
                age = now_dt - published_dt
                if age <= timedelta(days=14):
                    recent_bonus = 3
                elif age <= timedelta(days=60):
                    recent_bonus = 2
                elif age <= timedelta(days=365):
                    recent_bonus = 1
            return (
                official_bonus,
                recent_bonus,
                trusted_bonus,
                published_dt.timestamp() if published_dt is not None else 0,
            )

        snippets = []
        target_years = target_years or []
        target_year_tokens = {str(year) for year in target_years}
        ordered_items = sorted(items, key=_freshness_sort_key, reverse=True)
        for item in ordered_items:
            title = self._one_line(str(item.get("title", "") or ""), max_chars=120)
            body = self._one_line(str(item.get("body", "") or ""), max_chars=220)
            href = str(item.get("url") or item.get("href") or "").strip()
            published = self._one_line(str(item.get("date", "") or ""), max_chars=40)
            if not href or href in seen_links:
                continue
            if latest_product_query and self._is_low_signal_product_source(href):
                continue
            combined_text = f"{title} {body} {published}"
            if fresh_required and target_year_tokens:
                if not any(token in combined_text for token in target_year_tokens):
                    continue
            seen_links.add(href)
            date_line = f"\n  Date: {published}" if published else ""
            snippets.append(f"- {title}\n  {body}{date_line}\n  Source: {href}")
        return snippets

    def _serper_search(self, query: str, max_results: int, use_news: bool = False) -> List[Dict[str, str]]:
        if not self.serper_api_key:
            return []
        endpoint = "https://google.serper.dev/news" if use_news else "https://google.serper.dev/search"
        payload = {"q": query, "num": max(1, min(max_results, 10))}
        req = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"X-API-KEY": self.serper_api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.openai_web_timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._last_web_error = f"serper_{'news' if use_news else 'search'}: {exc}"
            return []

        bucket = data.get("news", []) if use_news else data.get("organic", [])
        items: List[Dict[str, str]] = []
        for item in bucket[:max_results]:
            items.append(
                {
                    "title": str(item.get("title", "") or ""),
                    "body": str(item.get("snippet", "") or ""),
                    "url": str(item.get("link", "") or ""),
                    "date": str(item.get("date", "") or ""),
                }
            )
        return items

    def _tavily_search(self, query: str, max_results: int, fresh_required: bool = False) -> List[Dict[str, str]]:
        if not self.tavily_api_key:
            return []
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "max_results": max(1, min(max_results, 10)),
            "search_depth": "advanced" if fresh_required else "basic",
            "include_answer": False,
            "include_raw_content": False,
        }
        req = Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=self.openai_web_timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self._last_web_error = f"tavily_search: {exc}"
            return []

        items: List[Dict[str, str]] = []
        for item in (data.get("results", []) or [])[:max_results]:
            items.append(
                {
                    "title": str(item.get("title", "") or ""),
                    "body": str(item.get("content", "") or ""),
                    "url": str(item.get("url", "") or ""),
                    "date": str(item.get("published_date", "") or ""),
                }
            )
        return items

    def _remember_web_context(
        self,
        session_id: str,
        query: str,
        search_query: str,
        context: str,
        fresh_required: bool,
        source_count: int,
    ):
        state = self._ensure_session_state(session_id)
        item = {
            "query": self._one_line(query, max_chars=140),
            "search_query": self._one_line(search_query, max_chars=180),
            "fresh_required": fresh_required,
            "source_count": source_count,
            "retrieved_at": datetime.now().isoformat(timespec="seconds"),
            "preview": self._one_line(context, max_chars=240),
        }
        with self._state_lock:
            state["web_history"].append(item)
            state["web_history"] = state["web_history"][-self.web_history_limit :]

    def _web_context(
        self,
        session_id: str,
        text_query: str,
        max_results: int = 5,
        fresh_required: bool = False,
        response_language: str = "ko",
        prefer_openai_web: bool = False,
        bypass_cache: bool = False,
        explicit_web_search: bool = False,
    ) -> str:
        # 검색 순서는 중요하다.
        # 빠른 캐시 확인 -> 외부 검색 조합 -> OpenAI 웹 fallback 순으로 두어야
        # 검색 품질 이슈가 생겼을 때 인수인계와 디버깅이 수월하다.
        now_intent = self._has_now_intent(text_query)
        search_query = self._build_web_query(text_query, fresh_required)
        normalized = self._normalize_search_query(search_query)
        cached = "" if bypass_cache else self._get_cached_web(normalized, fresh_required, response_language)
        if cached and not now_intent:
            self._remember_web_context(
                session_id,
                text_query,
                search_query,
                cached,
                fresh_required,
                len(self._extract_sources(cached)),
            )
            return cached

        try:
            seen_links = set()
            max_results = max(1, min(max_results, self.web_max_results))
            target_years = self._extract_target_years(text_query)
            latest_product_query = self._is_latest_product_query(text_query)
            prefer_news_results = self._prefer_news_results(text_query, fresh_required)
            overview_query = self._build_overview_query(text_query)
            include_overview_first = (
                fresh_required
                and not prefer_news_results
                and not self._is_live_data_query(text_query)
                and bool(overview_query)
            )
            snippets: List[str] = []
            direct_answer = ""
            direct_links: List[str] = []

            if fresh_required and prefer_openai_web:
                direct_answer, direct_links = self._direct_openai_web_answer(text_query, response_language)
                for url in direct_links[:max_results]:
                    seen_links.add(url)

            if include_overview_first:
                overview_items = self._serper_search(overview_query, min(2, max_results), use_news=False)
                snippets.extend(
                    self._format_web_items(
                        overview_items,
                        seen_links,
                        target_years=None,
                        fresh_required=False,
                        latest_product_query=latest_product_query,
                    )
                )

            if fresh_required and prefer_news_results:
                serper_news = self._serper_search(search_query, max_results, use_news=True)
                snippets.extend(
                    self._format_web_items(
                        serper_news,
                        seen_links,
                        target_years=target_years,
                        fresh_required=fresh_required,
                        latest_product_query=latest_product_query,
                    )
                )

            if len(snippets) < max_results:
                serper_text = self._serper_search(search_query, max_results, use_news=False)
                snippets.extend(
                    self._format_web_items(
                        serper_text,
                        seen_links,
                        target_years=target_years,
                        fresh_required=fresh_required,
                        latest_product_query=latest_product_query,
                    )
                )

            if len(snippets) < max_results and fresh_required and not prefer_news_results:
                serper_news = self._serper_search(search_query, max_results, use_news=True)
                snippets.extend(
                    self._format_web_items(
                        serper_news,
                        seen_links,
                        target_years=target_years,
                        fresh_required=fresh_required,
                        latest_product_query=latest_product_query,
                    )
                )

            if len(snippets) < max_results:
                tavily_items = self._tavily_search(search_query, max_results, fresh_required=fresh_required)
                snippets.extend(
                    self._format_web_items(
                        tavily_items,
                        seen_links,
                        target_years=target_years,
                        fresh_required=fresh_required,
                        latest_product_query=latest_product_query,
                    )
                )

            if direct_answer and direct_links and not explicit_web_search:
                preferred_links = direct_links[:max_results] or list(seen_links)[:max_results]
                return self._store_web_context_result(
                    normalized,
                    session_id,
                    text_query,
                    search_query,
                    direct_answer,
                    fresh_required,
                    response_language,
                    links=preferred_links,
                    source_count=len(preferred_links),
                    max_links=max_results,
                )

            if len(snippets) < max_results and fresh_required and not now_intent and not self._is_public_figure_query(text_query):
                relaxed_items = self._serper_search(text_query, max_results, use_news=False)
                snippets.extend(
                    self._format_web_items(
                        relaxed_items,
                        seen_links,
                        target_years=target_years,
                        fresh_required=fresh_required,
                        latest_product_query=latest_product_query,
                    )
                )

            context = "\n".join(snippets[:max_results]).strip()
            if context:
                return self._store_web_context_result(
                    normalized,
                    session_id,
                    text_query,
                    search_query,
                    context,
                    fresh_required,
                    response_language,
                    source_count=len(seen_links),
                )

            # Serper/Tavily 결과가 비면 OpenAI 웹 검색을 2차 폴백으로 시도한다.
            # 다만 "지금/최신/최근" 의도가 강하면 응답 속도를 위해 이 느린 폴백은 생략한다.
            if direct_answer:
                fallback_links = direct_links[:max_results] if direct_links else list(seen_links)[:max_results]
                return self._store_web_context_result(
                    normalized,
                    session_id,
                    text_query,
                    search_query,
                    direct_answer,
                    fresh_required,
                    response_language,
                    links=fallback_links,
                    source_count=len(fallback_links),
                    max_links=max_results,
                )

            if prefer_openai_web and not now_intent:
                direct_answer, direct_links = self._direct_openai_web_answer(text_query, response_language)
                if direct_answer:
                    return self._store_web_context_result(
                        normalized,
                        session_id,
                        text_query,
                        search_query,
                        direct_answer,
                        fresh_required,
                        response_language,
                        links=direct_links,
                        source_count=len(direct_links),
                        max_links=max_results,
                    )

            if cached:
                self._remember_web_context(
                    session_id,
                    text_query,
                    search_query,
                    cached,
                    fresh_required,
                    len(self._extract_sources(cached)),
                )
            return cached or ""
        except Exception as exc:
            self._last_web_error = f"web_context: {exc}"
            print(f"[agent] web search failed: {exc}")
            return cached or ""

    def _is_factual_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        if self._is_public_figure_query(query):
            return True
        return any(token in query for token in FACTUAL_CUES) or bool(self._extract_target_years(query))

    def _needs_fresh_data(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        current_year = datetime.now().year
        year_hits = [int(year) for year in RE_YEAR.findall(query)]
        has_now_intent = self._has_now_intent(text_query)
        asks_recent = any(
            token in query
            for token in [
                "\ud604\uc7ac",
                "\uc9c0\uae08",
                "\uc694\uc998",
                "\uc624\ub298",
                "\uc774\ubc88",
                "\ucd5c\uc2e0",
                "\ucd5c\uadfc",
                "\uc2e4\uc2dc\uac04",
                "\uc5c5\ub370\uc774\ud2b8",
                "latest",
                "current",
                "now",
                "today",
                "news",
                "update",
            ]
        )
        time_sensitive_tokens = [
            "\uac00\uaca9",
            "\ud658\uc728",
            "\uc8fc\uac00",
            "\ub0a0\uc528",
            "\uc77c\uc815",
            "\uacb0\uacfc",
            "\uc810\uc218",
            "\uc2dc\uc138",
            "\uc2e4\uc801",
            "price",
            "stock",
            "rate",
            "weather",
            "schedule",
            "result",
            "score",
            "market",
        ]
        time_sensitive = any(token in query for token in time_sensitive_tokens)
        has_past_year_only = bool(year_hits) and all(year < current_year for year in year_hits)
        if has_now_intent and len(query.strip()) >= 3:
            return True
        if self._is_public_figure_query(text_query) and not has_past_year_only:
            return True
        if time_sensitive and not has_past_year_only:
            return True
        return self._is_factual_query(text_query) and (asks_recent or any(year >= current_year for year in year_hits))

    def _is_live_data_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        live_data_tokens = [
            "실시간",
            "현재",
            "지금",
            "오늘",
            "최신",
            "최근",
            "주가",
            "시세",
            "가격",
            "환율",
            "날씨",
            "스코어",
            "점수",
            "결과",
            "일정",
            "stock",
            "price",
            "market",
            "rate",
            "weather",
            "score",
            "result",
            "schedule",
            "today",
            "latest",
            "current",
            "now",
        ]
        return any(token in query for token in live_data_tokens)

    def _should_use_web_search(self, text_query: str) -> bool:
        query = (text_query or "").strip()
        if not query:
            return False
        if self._has_now_intent(query):
            return True
        if self._is_public_figure_query(query):
            return True
        if self._is_company_query(query):
            return False
        return self._needs_fresh_data(query) or self._is_factual_query(query)

    def _detect_emotion(self, text_query: str) -> str:
        query = (text_query or "").lower()
        emotion_keywords = {
            "anxious": ["\ubd88\uc548", "\uac71\uc815", "\ucd08\uc870", "anxious", "nervous", "worried"],
            "frustrated": ["\ub2f5\ub2f5", "\uc9dc\uc99d", "\ud654\ub098", "frustrated", "annoyed", "angry"],
            "sad": ["\uc2ac\ud37c", "\uc6b0\uc6b8", "\ud798\ub4e4", "sad", "depressed", "down"],
            "confused": ["\ubaa8\ub974\uaca0", "\ud5f7\uac08", "\uc774\ud574\uac00 \uc548", "confused", "not sure"],
            "stressed": ["\uc2a4\ud2b8\ub808\uc2a4", "\uc9c0\uce68", "\ubc84\uac70", "stressed", "burnout"],
            "positive": ["\uae30\uc068", "\uc88b\uc544", "\uac10\uc0ac", "happy", "great", "excited"],
        }
        for emotion, keywords in emotion_keywords.items():
            if any(token in query for token in keywords):
                return emotion
        return "neutral"

    def _high_risk_warning(self, text_query: str) -> str:
        query = (text_query or "").lower()
        high_risk_tokens = [
            "자살",
            "자해",
            "죽이는",
            "폭탄",
            "총기",
            "마약",
            "테러",
            "살인",
            "suicide",
            "self-harm",
            "bomb",
            "gun",
            "drug",
            "terror",
            "kill",
            "murder",
        ]
        if any(token in query for token in high_risk_tokens):
            return "주의: 민감하거나 위험할 수 있는 주제입니다. 사실 확인과 안전 수칙을 꼭 확인해 주세요."
        return ""

    def _build_prompt(
        self,
        text_query: str,
        memory: str,
        knowledge: str,
        web: str,
        fresh_required: bool,
        empathy_level: str,
        detected_emotion: str,
        response_language: str = "ko",
    ) -> str:
        current_date = datetime.now().strftime("%Y-%m-%d")
        answer_language_line = (
            "Answer in English unless the user asks otherwise."
            if self._normalize_response_language(response_language) == "en"
            else "Answer in Korean unless the user asks otherwise."
        )
        freshness_rule = (
            "For recent facts, use [Web Search Context] first. If it is missing, clearly say the latest data could not be verified."
            if fresh_required
            else "Use knowledge base and memory first, then web context when provided."
        )
        empathy_rule = {
            "low": "Keep empathy minimal and focus on concise professional guidance.",
            "high": "Acknowledge user feelings in one or two warm sentences, then provide supportive guidance.",
        }.get(empathy_level, "Show balanced empathy with one short caring sentence when needed.")
        emotion_rule = (
            f"Detected user emotion: {detected_emotion}. "
            "If it is not neutral, acknowledge it naturally and avoid generic consolation."
        )

        return f"""You are a Smart Factory AI assistant.
{answer_language_line}
Speak naturally, like a strong production-grade chat assistant.
Guidelines:
- Be accurate, practical, and easy to follow.
- Keep the tone warm and professional.
- If the user sounds worried or confused, start with one short empathetic sentence.
- Prefer natural paragraphs. Use bullets only when they improve clarity.
- If information is uncertain, say so clearly and suggest how to verify it.
- Do not use section labels such as summary, details, or next steps.
- If [Knowledge Base Context] is present and relevant, prioritize it over generic background knowledge.
- When using local knowledge, explicitly reflect the retrieved content and mention source labels like [file.pdf#p2].
- If web search includes recent facts, prioritize it for latest data and include relevant source links naturally.
- When web context contains both background and recent updates, start with a short plain-language introduction to the topic, then explain the latest developments or articles.
- Combine memory, knowledge, and web search when they all matter.
- Never state an exact current number, officeholder, schedule, or status unless it is explicitly supported by [Web Search Context].
- If [Web Search Context] does not verify the exact latest fact, say it could not be verified instead of guessing.
- Do not use stale prior knowledge for current or real-time facts.
Today: {current_date}
Rule: {freshness_rule}
Empathy: {empathy_rule}
Emotion: {emotion_rule}

[Conversation Memory]
{memory}

[Knowledge Base Context]
{knowledge or '(No local knowledge context)'}

[Web Search Context]
{web or '(Web search disabled or no results)'}

When web context is available, include key source links in your answer.
User question: {text_query}
"""

    def _format_conservative_web_answer(self, web_context: str, response_language: str = "ko") -> str:
        text = self._sanitize_response_text(web_context or "").strip()
        if not text:
            return ""
        if "Source:" in text and "[Sources]" not in text:
            lead = (
                "Here is a summary based on the latest web search results."
                if self._normalize_response_language(response_language) == "en"
                else "최신 웹 검색 결과를 바탕으로 확인한 내용입니다."
            )
            return f"{lead}\n\n{text}"
        return text

    def _extract_sources(self, web_context: str) -> List[str]:
        links: List[str] = []
        text = web_context or ""
        for line in text.splitlines():
            if "Source:" in line:
                url = line.split("Source:", 1)[1].strip()
            else:
                stripped = line.strip()
                if not stripped.startswith("- http"):
                    continue
                url = stripped[2:].strip()
            if url and url not in links:
                links.append(url)
        # 마지막 폴백으로 모델 출력이나 마크다운 내부의 인라인 URL도 수집한다.
        for url in RE_INLINE_URL.findall(text):
            cleaned = url.strip().rstrip(".,;")
            if cleaned and cleaned not in links:
                links.append(cleaned)
        return links

    def _format_citation_block(self, links: List[str]) -> str:
        if not links:
            return ""
        return "\n\n[Sources]\n" + "\n".join(f"- {url}" for url in links)

    def _is_trusted_fresh_source(self, url: str) -> bool:
        host = _normalized_host(url)
        return bool(host) and _host_matches(host, TRUSTED_FRESH_DOMAINS)

    def _is_official_product_source(self, url: str) -> bool:
        host = _normalized_host(url)
        return bool(host) and _host_matches(host, OFFICIAL_PRODUCT_DOMAINS)

    def _is_low_signal_product_source(self, url: str) -> bool:
        host = _normalized_host(url)
        return bool(host) and _host_matches(host, LOW_SIGNAL_DOMAINS)

    def _is_official_public_source(self, url: str) -> bool:
        host = _normalized_host(url)
        return bool(host) and _host_matches(host, OFFICIAL_PUBLIC_DOMAINS)

    def _direct_openai_web_answer(self, text_query: str, response_language: str = "ko") -> Tuple[str, List[str]]:
        if OpenAI is None or not self.openai_api_key:
            return "", []

        try:
            client = self._get_openai_client("openai")
        except Exception:
            return "", []

        responses_api = getattr(client, "responses", None)
        if responses_api is None or not hasattr(responses_api, "create"):
            return "", []

        today = datetime.now().strftime("%Y-%m-%d")
        target_years = self._extract_target_years(text_query)
        target_year_line = f"Target year(s): {', '.join(str(year) for year in target_years)}\n" if target_years else ""
        answer_language_line = (
            "Answer in English unless the user asks otherwise.\n"
            if self._normalize_response_language(response_language) == "en"
            else "Answer in Korean unless the user asks otherwise.\nEven if sources are in English, write the final answer in Korean.\n"
        )
        prompt = (
            "Please answer with language that matches the user's question. If the question is in Korean, answer in Korean. If the question is in English, answer in English.\n"
            "Use web search to answer with the most recent verifiable information.\n"
            f"{answer_language_line}"
            "If the question is time-sensitive, mention the exact date in the answer.\n"
            "Use the newest reliable sources available and keep source links.\n"
            "Always include at least 2 direct source URLs (https://...) in the final answer.\n"
            "Do not omit source links.\n"
            "For political officeholder questions (e.g., president/prime minister), verify the current officeholder as of today using official or major reliable sources.\n"
            "For public figure questions (e.g., celebrities), verify with recent reliable sources and include concrete dates for key facts.\n"
            "If country is ambiguous, infer from user language context but state the country explicitly.\n"
            "If the user asks for a specific year such as 2026, do not present older-year data as if it were current for that year.\n"
            "If verified data for the requested year is not available, explicitly say the requested year's latest data could not be verified.\n"
            f"Today: {today}\n"
            f"{target_year_line}"
            f"Question: {self._build_web_query(text_query, True)}"
        )

        response = None
        retries = max(1, self.openai_web_retries)
        for attempt in range(retries):
            try:
                response = responses_api.create(
                    model=self.openai_web_model,
                    input=prompt,
                    tools=[{"type": "web_search_preview"}],
                    timeout=self.openai_web_timeout_sec,
                )
                break
            except Exception as exc:
                self._last_web_error = f"openai_web: {exc}"
                print(f"[agent] openai web answer failed ({attempt + 1}/{retries}): {exc}")
                if attempt < retries - 1:
                    time.sleep(self.web_retry_backoff_sec * (attempt + 1))
        if response is None:
            return "", []

        answer = (getattr(response, "output_text", "") or "").strip()
        links: List[str] = []

        try:
            outputs = getattr(response, "output", None) or []
            for item in outputs:
                for content in getattr(item, "content", None) or []:
                    for annotation in getattr(content, "annotations", None) or []:
                        url = (getattr(annotation, "url", "") or "").strip()
                        if url and url not in links:
                            links.append(url)
        except Exception:
            pass

        if not links and answer:
            for url in RE_INLINE_URL_ALT.findall(answer):
                cleaned = url.strip().rstrip(".,;")
                if cleaned and cleaned not in links:
                    links.append(cleaned)
        if not links and answer:
            search_query = self._build_web_query(text_query, True)
            supplemental: List[Dict[str, str]] = []
            supplemental.extend(self._serper_search(search_query, 3, use_news=True))
            if len(supplemental) < 3:
                supplemental.extend(self._serper_search(search_query, 3, use_news=False))
            if len(supplemental) < 3:
                supplemental.extend(self._tavily_search(search_query, 3, fresh_required=True))
            for item in supplemental:
                candidate = str(item.get("url") or "").strip()
                if candidate and candidate not in links:
                    links.append(candidate)
                if len(links) >= 3:
                    break

        if self._is_live_data_query(text_query) and self._has_placeholder_live_value(answer):
            answer = ""

        target_years = self._extract_target_years(text_query)
        now_intent = self._has_now_intent(text_query)
        public_office_query = self._is_public_office_query(text_query)
        if target_years and answer:
            trusted_links = [url for url in links if self._is_trusted_fresh_source(url)]
            if trusted_links:
                links = trusted_links
        if public_office_query:
            official_links = [url for url in links if self._is_official_public_source(url)]
            trusted_links = [url for url in links if self._is_trusted_fresh_source(url)]
            if official_links:
                merged_links: List[str] = []
                for url in official_links + trusted_links:
                    if url and url not in merged_links:
                        merged_links.append(url)
                links = merged_links
            elif len(trusted_links) >= 2:
                links = trusted_links
            else:
                # 공식/신뢰 출처가 충분치 않으면 기술적 검증 실패를 내보내지 말고
                # 상위 검색 조합 경로가 다른 폴백을 시도하도록 빈 결과로 돌린다.
                return "", []

        return answer, links

    def _sanitize_response_text(self, text: str) -> str:
        patterns = [
            r"(?im)^\s*\*{0,2}\s*(?:[-*]|\d+[.)])?\s*(?:summary|details|next\s*steps?)\s*\*{0,2}\s*:?\s*$",
        ]
        sanitized = text
        for pattern in patterns:
            sanitized = re.sub(pattern, "", sanitized)
        return re.sub(r"\n{3,}", "\n\n", sanitized).strip()

    def _has_placeholder_live_value(self, text: str) -> bool:
        value = str(text or "")
        if not value:
            return False
        placeholder_patterns = [
            r"\bX(?:[Xx,\-./ ]*X)+\b",
            r"\bN/?A\b",
            r":\s*$",
        ]
        return any(re.search(pattern, value, flags=re.IGNORECASE | re.MULTILINE) for pattern in placeholder_patterns)

    def _friendly_connection_error(self, error_msg: str) -> str:
        message = (error_msg or "").lower()
        if "strict_fresh_public_office" in message or "minimum official source links were not satisfied" in message:
            return (
                "현재 공직자 정보는 공식 출처 확인이 충분하지 않아 답변을 보류했습니다. "
                "잠시 후 다시 시도하거나 웹 검색을 켠 뒤 다시 질문해 주세요."
            )
        if "10013" in message or "access" in message and "socket" in message:
            return (
                "외부 네트워크 소켓 연결이 차단되어 OpenAI 또는 Web Search에 접속하지 못했습니다. "
                "방화벽, 보안 프로그램, 회사망 정책, 또는 실행 환경 제한을 확인해 주세요."
            )
        if "timed out" in message or "timeout" in message:
            return (
                "OpenAI Web Search 응답이 시간 안에 오지 않았습니다. "
                "잠시 후 다시 시도하거나, 타임아웃 값을 늘려서 사용해 주세요."
            )
        if "connection error" in message or "connecterror" in message:
            return (
                "OpenAI 또는 Web Search 서버와 연결하지 못했습니다. "
                "인터넷 연결과 방화벽, API 접속 가능 여부를 확인해 주세요."
            )
        return f"An error occurred while generating the response: {error_msg}"

    def _buffered_stream(self, llm, prompt: str):
        raw_text = ""
        emitted_text = ""
        pending = ""
        for chunk in llm.stream(prompt):
            if not chunk or not getattr(chunk, "content", None):
                continue
            raw_text += chunk.content
            sanitized = self._sanitize_response_text(raw_text)
            if not sanitized.startswith(emitted_text):
                emitted_text = ""
                pending = ""
            delta = sanitized[len(emitted_text) :]
            if not delta:
                continue

            emitted_text += delta
            pending += delta
            boundary = max(pending.rfind("\n"), pending.rfind(". "), pending.rfind("? "), pending.rfind("! "))
            if boundary >= 0 or len(pending) >= 120:
                emit_now = pending if boundary < 0 else pending[: boundary + 1]
                pending = "" if boundary < 0 else pending[boundary + 1 :]
                if emit_now:
                    yield emit_now
        if pending:
            yield pending

    def _buffered_openai_stream(self, client, model: str, prompt: str):
        raw_text = ""
        emitted_text = ""
        pending = ""
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            stream=True,
        )
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None)
            if not content:
                continue

            raw_text += content
            sanitized = self._sanitize_response_text(raw_text)
            if not sanitized.startswith(emitted_text):
                emitted_text = ""
                pending = ""
            new_delta = sanitized[len(emitted_text) :]
            if not new_delta:
                continue

            emitted_text += new_delta
            pending += new_delta
            boundary = max(pending.rfind("\n"), pending.rfind(". "), pending.rfind("? "), pending.rfind("! "))
            if boundary >= 0 or len(pending) >= 120:
                emit_now = pending if boundary < 0 else pending[: boundary + 1]
                pending = "" if boundary < 0 else pending[boundary + 1 :]
                if emit_now:
                    yield emit_now
        if pending:
            yield pending

    def _prepare_context(
        self,
        session_id: str,
        text_query: str,
        use_web_search: bool,
        response_language: str = "ko",
        disable_auto_web: bool = False,
        prefer_openai_web: bool = False,
    ) -> Tuple[str, str, bool]:
        self._last_web_error = ""
        detected_emotion = self._detect_emotion(text_query)
        fresh_required = self._needs_fresh_data(text_query)
        # 프런트가 명시적으로 요청하지 않아도 시의성이 중요한 질문은
        # 자동 웹 검색으로 최신 컨텍스트를 붙일 수 있게 opt-out 방식으로 둔다.
        auto_web = False if disable_auto_web else self._should_use_web_search(text_query)
        force_web = use_web_search or auto_web
        web = (
            self._web_context(
                session_id,
                text_query,
                max_results=self.web_max_results,
                fresh_required=fresh_required,
                response_language=response_language,
                prefer_openai_web=prefer_openai_web,
                bypass_cache=use_web_search,
                explicit_web_search=use_web_search,
            )
            if force_web
            else ""
        )
        return web, detected_emotion, fresh_required

    def get_memory_snapshot(self, session_id: str = "") -> Dict[str, object]:
        key = self._session_key(session_id)
        state = self._ensure_session_state(key)
        with self._state_lock:
            chat_history = list(state.get("chat_history", []))
            knowledge_memory = list(state.get("knowledge_memory", []))
            web_history = list(state.get("web_history", []))
            memory_summary = str(state.get("memory_summary", "") or "")

        return {
            "session_id": key,
            "chat_turns": len(chat_history) // 2,
            "message_count": len(chat_history),
            "memory_summary": memory_summary,
            "recent_messages": chat_history[-6:],
            "knowledge_memory": knowledge_memory[-4:],
            "web_history": web_history[-4:],
        }

    def get_web_diagnostics(self, probe_query: str = "current market data now") -> Dict[str, object]:
        started_at = time.time()
        direct_answer, direct_links = self._direct_openai_web_answer(probe_query)
        elapsed_ms = int((time.time() - started_at) * 1000)
        return {
            "probe_query": probe_query,
            "openai_api_key_set": bool(self.openai_api_key),
            "openai_web_model": self.openai_web_model,
            "openai_web_timeout_sec": self.openai_web_timeout_sec,
            "openai_web_retries": self.openai_web_retries,
            "web_fresh_source_mode": self.web_fresh_source_mode,
            "direct_answer_ok": bool(direct_answer),
            "direct_links_count": len(direct_links),
            "direct_links": direct_links[:5],
            "elapsed_ms": elapsed_ms,
            "last_web_error": self._last_web_error,
        }

    def get_ai_streaming_response(
        self,
        text_query: str,
        provider: str = "openai",
        use_web_search: bool = False,
        disable_auto_web: bool = False,
        empathy_level: str = "balanced",
        session_id: str = "",
        response_language: str = "ko",
    ):
        # 메인 실행 흐름
        # 1) 빠른 우회 응답 가능한지 먼저 확인
        # 2) 필요하면 최신 웹 컨텍스트 준비
        # 3) 메모리/지식/웹 정보를 합쳐 전체 LLM 응답 생성
        provider = (provider or "openai").lower()
        response_language = self._resolve_response_language(response_language, text_query)
        session_key = self._session_key(session_id)
        sources: List[str] = []
        warning_banner = self._high_risk_warning(text_query)
        if warning_banner:
            yield f"{warning_banner}\n\n"
        direct_ocr_answer = self._direct_ocr_text_answer(text_query)
        if direct_ocr_answer:
            self._remember_direct_answer(session_key, text_query, direct_ocr_answer)
            yield direct_ocr_answer
            return
        direct_company_answer = self._direct_company_answer(text_query)
        if direct_company_answer:
            self._remember_direct_answer(session_key, text_query, direct_company_answer)
            yield direct_company_answer
            return
        direct_knowledge_answer = self._direct_knowledge_answer(text_query)
        if direct_knowledge_answer:
            self._remember_direct_answer(session_key, text_query, direct_knowledge_answer)
            yield direct_knowledge_answer
            return

        fresh_required = use_web_search or self._needs_fresh_data(text_query)
        now_intent = self._has_now_intent(text_query)
        direct_cache_key = self._normalize_search_query(self._build_web_query(text_query, fresh_required))
        skip_repeated_openai_web = not (use_web_search or fresh_required)

        if fresh_required and not use_web_search:
            cached_answer, cached_links = self._get_cached_answer(direct_cache_key, response_language)
            if not now_intent and cached_answer:
                # 같은 최신 질문이 반복되면 최근 답변을 재사용하되,
                # "지금 당장" 성격이 강한 질문은 재조회 기대가 있어 캐시를 피한다.
                self._remember(session_key, "user", text_query)
                yield cached_answer
                final_cached = cached_answer
                if cached_links:
                    source_block = self._format_citation_block(cached_links)
                    yield source_block
                    final_cached = f"{final_cached}{source_block}"
                self._remember(session_key, "assistant", final_cached)
                return

        llm = self._get_llm(provider)
        memory = self._history_block(session_key)
        knowledge = self._knowledge_context(session_key, text_query)
        if use_web_search:
            knowledge = ""
        web, detected_emotion, fresh_required = self._prepare_context(
            session_key,
            text_query,
            use_web_search,
            response_language=response_language,
            disable_auto_web=disable_auto_web,
            prefer_openai_web=not skip_repeated_openai_web,
        )
        sources = self._extract_sources(web) if web else []

        if use_web_search and fresh_required and self._is_live_data_query(text_query) and web:
            # 실시간성 사실 질문은 모델이 재서술하다 왜곡할 수 있으므로
            # 정리된 웹 컨텍스트를 기반으로 바로 답하게 한다.
            final_answer = self._format_conservative_web_answer(web, response_language)
            final_answer = self._compose_answer_with_sources(final_answer, sources)
            if final_answer:
                self._remember_direct_answer(session_key, text_query, final_answer)
                yield final_answer
                return

        prompt = self._build_prompt(
            text_query=text_query,
            memory=memory,
            knowledge=knowledge,
            web=web,
            fresh_required=fresh_required,
            empathy_level=empathy_level,
            detected_emotion=detected_emotion,
            response_language=response_language,
        )

        self._remember(session_key, "user", text_query)
        chunks: List[str] = []

        try:
            if llm is not None:
                stream_iter = self._buffered_stream(llm, prompt)
            elif provider == "openai":
                client = self._get_openai_client("openai")
                stream_iter = self._buffered_openai_stream(client, self.openai_model, prompt)
            else:
                raise RuntimeError("Selected provider is unavailable in the current environment")

            for part in stream_iter:
                chunks.append(part)
                yield part
        except Exception as exc:
            error_msg = str(exc)
            print(f"[agent] llm stream failed: {error_msg}")
            if "insufficient_quota" in error_msg:
                yield "API quota is insufficient. Please check billing or try again later."
            elif "rate_limit" in error_msg:
                yield "The model is temporarily rate-limited. Please try again in a moment."
            else:
                yield self._friendly_connection_error(error_msg)
            return

        final_answer = self._sanitize_response_text("".join(chunks))
        if sources:
            source_block = self._format_citation_block(sources)
            yield source_block
            final_answer = f"{final_answer}{source_block}"
        if final_answer:
            self._remember(session_key, "assistant", final_answer)


agent_instance = CSAgent()
