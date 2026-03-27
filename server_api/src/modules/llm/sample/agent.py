import os
import json
import re
import time
from datetime import datetime
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

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


class _DirectOpenAIEmbeddings(Embeddings):
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

        self.retriever = None
        self.local_knowledge_docs: List[Dict[str, object]] = []
        self._llm_cache: Dict[str, object] = {}
        self._client_cache: Dict[str, object] = {}
        self._web_cache: Dict[str, Dict[str, object]] = {}
        self._answer_cache: Dict[str, Dict[str, object]] = {}
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
        normalized = re.sub(r"\s+", "-", (session_id or "").strip())
        normalized = re.sub(r"[^0-9A-Za-z._-]", "", normalized)
        return normalized[:80] or "default"

    def _ensure_session_state(self, session_id: str = "") -> Dict[str, object]:
        key = self._session_key(session_id)
        with self._state_lock:
            if key not in self._session_state:
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
        normalized = re.sub(r"\s+", " ", (text or "")).strip()
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
                content = re.sub(
                    r"(?im)^\s*(?:[-*]|\d+[.)])?\s*(?:summary|details|next steps?)\s*:?\s*$",
                    "",
                    content,
                )
                content = re.sub(r"\n{3,}", "\n\n", content).strip()
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _tokenize_korean_english(self, text: str) -> set:
        tokens = re.findall(r"[0-9A-Za-z]{2,}|[\uac00-\ud7a3]{2,}", (text or "").lower())
        return set(tokens)

    def _normalize_knowledge_query(self, text_query: str) -> str:
        normalized = re.sub(r"\s+", " ", (text_query or "")).strip().lower()
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
        return [int(year) for year in re.findall(r"(20\d{2})", text or "")]

    def _has_now_intent(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        tokens = [
            "\ud604\uc7ac",
            "\uc9c0\uae08",
            "\uc624\ub298",
            "\uc694\uc998",
            "\ucd5c\uadfc",
            "\ucd5c\uc2e0",
            "\uadfc\ud669",
            "\uc5c5\ub370\uc774\ud2b8",
            "current",
            "now",
            "today",
            "latest",
            "recent",
            "update",
        ]
        return any(token in query for token in tokens)

    def _is_broad_knowledge_query(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        broad_keywords = [
            "\uc804\uccb4",
            "\uc804\ubd80",
            "\ubaa8\ub4e0",
            "\uc815\ub9ac",
            "\uc694\uc57d",
            "all",
            "full",
            "entire",
            "summary",
        ]
        return any(keyword in query for keyword in broad_keywords)

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
        normalized_context = re.sub(r"\s+", " ", context).strip()
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
        normalized_content = re.sub(r"\s+", " ", (content or "")).strip().lower()
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
            normalized_phrase = re.sub(r"\s+", " ", (retrieval_query or "")).strip().lower()

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
        normalized = re.sub(r"\s+", " ", (value or "")).strip()
        replacements = {
            "주식회시": "주식회사",
        }
        for before, after in replacements.items():
            normalized = normalized.replace(before, after)
        return normalized

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
        query = re.sub(r"\s+", " ", (text_query or "")).strip().lower()
        query = re.sub(r"[\"'`]+", "", query)
        return query[:200]

    def _cache_key(self, normalized_query: str, fresh_required: bool) -> str:
        return f"{normalized_query}|fresh={int(fresh_required)}" if normalized_query else ""

    def _get_cached_web(self, normalized_query: str, fresh_required: bool) -> str:
        if not normalized_query:
            return ""
        cache_key = self._cache_key(normalized_query, fresh_required)
        entry = self._web_cache.get(cache_key)
        if not entry:
            return ""

        cached_at = float(entry.get("at", 0.0))
        ttl = self.web_fresh_cache_ttl_sec if fresh_required else self.web_cache_ttl_sec
        if (time.time() - cached_at) > ttl:
            self._web_cache.pop(cache_key, None)
            return ""
        return str(entry.get("value", "") or "")

    def _set_cached_web(self, normalized_query: str, value: str, fresh_required: bool):
        if not normalized_query:
            return
        cache_key = self._cache_key(normalized_query, fresh_required)
        self._web_cache[cache_key] = {"value": value, "at": time.time()}
        if len(self._web_cache) > 80:
            oldest_key = min(self._web_cache, key=lambda key: float(self._web_cache[key].get("at", 0.0)))
            self._web_cache.pop(oldest_key, None)

    def _get_cached_answer(self, normalized_query: str) -> Tuple[str, List[str]]:
        if not normalized_query:
            return "", []
        entry = self._answer_cache.get(normalized_query)
        if not entry:
            return "", []
        cached_at = float(entry.get("at", 0.0))
        if (time.time() - cached_at) > self.answer_cache_ttl_sec:
            self._answer_cache.pop(normalized_query, None)
            return "", []
        answer = str(entry.get("answer", "") or "")
        links = [str(link) for link in (entry.get("links", []) or []) if link]
        return answer, links

    def _set_cached_answer(self, normalized_query: str, answer: str, links: List[str]):
        if not normalized_query or not answer:
            return
        self._answer_cache[normalized_query] = {
            "answer": answer,
            "links": links[: self.web_max_results],
            "at": time.time(),
        }
        if len(self._answer_cache) > 80:
            oldest_key = min(self._answer_cache, key=lambda key: float(self._answer_cache[key].get("at", 0.0)))
            self._answer_cache.pop(oldest_key, None)

    def _build_web_query(self, text_query: str, fresh_required: bool) -> str:
        query = re.sub(r"\s+", " ", (text_query or "")).strip()
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
        if re.search(r"20\d{2}", query):
            current_tokens = [current.strftime("%Y-%m-%d"), "today", "latest", "current"]
        return f"{query} {' '.join(current_tokens)}".strip()

    def _build_overview_query(self, text_query: str) -> str:
        query = re.sub(r"\s+", " ", (text_query or "")).strip()
        if not query:
            return ""
        overview = re.sub(
            r"\b(today|latest|current|recent|news|article|headline|report|press\s+release|now)\b",
            " ",
            query,
            flags=re.IGNORECASE,
        )
        overview = re.sub(r"(오늘|최신|현재|최근|뉴스|기사|헤드라인|보도|속보)", " ", overview)
        overview = re.sub(r"\s+", " ", overview).strip(" ,.-")
        return overview or query

    def _format_web_items(
        self,
        items: List[Dict[str, str]],
        seen_links: set,
        target_years: List[int] | None = None,
        fresh_required: bool = False,
    ) -> List[str]:
        snippets = []
        target_years = target_years or []
        for item in items:
            title = self._one_line(str(item.get("title", "") or ""), max_chars=120)
            body = self._one_line(str(item.get("body", "") or ""), max_chars=220)
            href = str(item.get("url") or item.get("href") or "").strip()
            published = self._one_line(str(item.get("date", "") or ""), max_chars=40)
            if not href or href in seen_links:
                continue
            combined_text = f"{title} {body} {published}"
            if fresh_required and target_years:
                if not any(str(year) in combined_text for year in target_years):
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
        prefer_openai_web: bool = False,
    ) -> str:
        now_intent = self._has_now_intent(text_query)
        search_query = self._build_web_query(text_query, fresh_required)
        normalized = self._normalize_search_query(search_query)
        cached = self._get_cached_web(normalized, fresh_required)
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
            prefer_news_results = self._is_news_query(text_query)
            overview_query = self._build_overview_query(text_query)
            include_overview_first = (
                fresh_required
                and not prefer_news_results
                and not self._is_live_data_query(text_query)
                and bool(overview_query)
            )
            snippets: List[str] = []

            if fresh_required and prefer_openai_web:
                direct_answer, direct_links = self._direct_openai_web_answer(text_query)
                if direct_answer and direct_links:
                    for url in direct_links[:max_results]:
                        seen_links.add(url)
                    context = direct_answer + self._format_citation_block(direct_links[:max_results])
                    self._set_cached_web(normalized, context, fresh_required)
                    self._remember_web_context(session_id, text_query, search_query, context, fresh_required, len(direct_links))
                    return context

            if include_overview_first:
                overview_items = self._serper_search(overview_query, min(2, max_results), use_news=False)
                snippets.extend(
                    self._format_web_items(
                        overview_items,
                        seen_links,
                        target_years=None,
                        fresh_required=False,
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
                    )
                )

            if len(snippets) < max_results and fresh_required and not now_intent and not self._is_public_figure_query(text_query):
                relaxed_items = self._serper_search(text_query, max_results, use_news=False)
                snippets.extend(
                    self._format_web_items(
                        relaxed_items,
                        seen_links,
                        target_years=target_years,
                        fresh_required=fresh_required,
                    )
                )

            context = "\n".join(snippets[:max_results]).strip()
            if context:
                self._set_cached_web(normalized, context, fresh_required)
                self._remember_web_context(session_id, text_query, search_query, context, fresh_required, len(seen_links))
                return context

            # If Serper/Tavily returned nothing, try OpenAI web search as a secondary fallback.
            # For explicit "now/latest/recent" intent, skip this slow fallback to keep response fast.
            if prefer_openai_web and not now_intent:
                direct_answer, direct_links = self._direct_openai_web_answer(text_query)
                if direct_answer:
                    context = direct_answer
                    if direct_links:
                        context = context + self._format_citation_block(direct_links[:max_results])
                    self._set_cached_web(normalized, context, fresh_required)
                    self._remember_web_context(
                        session_id,
                        text_query,
                        search_query,
                        context,
                        fresh_required,
                        len(direct_links),
                    )
                    return context

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
        factual_cues = [
            "\ucd5c\uc2e0",
            "\ucd5c\uadfc",
            "\uc2e4\uc2dc\uac04",
            "\uc5c5\ub370\uc774\ud2b8",
            "\ub274\uc2a4",
            "\uae30\uc0ac",
            "\ubc1c\ud45c",
            "\uc77c\uc815",
            "\uacb0\uacfc",
            "\uc810\uc218",
            "\uc8fc\uac00",
            "\uac00\uaca9",
            "\ud658\uc728",
            "\ud1b5\uacc4",
            "\ub370\uc774\ud130",
            "\ube44\uad50",
            "\uc21c\uc704",
            "\ub204\uad6c",
            "\uc5b8\uc81c",
            "\uc5b4\ub514",
            "\ubb34\uc5c7",
            "news",
            "price",
            "stock",
            "weather",
            "schedule",
            "result",
            "rate",
            "data",
            "compare",
            "ranking",
            "who",
            "when",
            "where",
            "what",
            "president",
            "prime minister",
            "celebrity",
            "actor",
            "singer",
        ]
        return any(token in query for token in factual_cues) or bool(self._extract_target_years(query))

    def _needs_fresh_data(self, text_query: str) -> bool:
        query = (text_query or "").lower()
        current_year = datetime.now().year
        year_hits = [int(year) for year in re.findall(r"(20\d{2})", query)]
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
    ) -> str:
        current_date = datetime.now().strftime("%Y-%m-%d")
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
Answer in Korean unless the user asks otherwise.
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
        # Fallback: capture inline URLs from model outputs or markdown text.
        for url in re.findall(r"https?://[^\s)\]>\"']+", text):
            cleaned = url.strip().rstrip(".,;")
            if cleaned and cleaned not in links:
                links.append(cleaned)
        return links

    def _format_citation_block(self, links: List[str]) -> str:
        if not links:
            return ""
        return "\n\n[Sources]\n" + "\n".join(f"- {url}" for url in links)

    def _is_trusted_fresh_source(self, url: str) -> bool:
        try:
            host = (urlparse(url).netloc or "").lower()
        except Exception:
            return False
        if host.startswith("www."):
            host = host[4:]
        trusted_domains = [
            "go.kr",
            "korea.kr",
            "gov",
            "samsung.com",
            "newspim.com",
            "yonhapnews.co.kr",
            "nikkei.com",
            "thelec.kr",
            "digitimes.com",
            "reuters.com",
            "apnews.com",
            "bbc.com",
            "bloomberg.com",
            "wsj.com",
            "ft.com",
            "cnbc.com",
            "investing.com",
            "marketwatch.com",
            "yna.co.kr",
            "newsis.com",
            "kbs.co.kr",
            "sbs.co.kr",
            "chosun.com",
            "joongang.co.kr",
            "donga.com",
            "hankyung.com",
            "mk.co.kr",
        ]
        return any(host == domain or host.endswith(f".{domain}") for domain in trusted_domains)

    def _is_official_public_source(self, url: str) -> bool:
        try:
            host = (urlparse(url).netloc or "").lower()
        except Exception:
            return False
        if host.startswith("www."):
            host = host[4:]
        official_domains = [
            "go.kr",
            "korea.kr",
            "gov",
            "whitehouse.gov",
            "congress.gov",
            "senate.gov",
            "house.gov",
            "state.gov",
            "europa.eu",
            "gov.uk",
        ]
        return any(host == domain or host.endswith(f".{domain}") for domain in official_domains)

    def _direct_openai_web_answer(self, text_query: str) -> Tuple[str, List[str]]:
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
        prompt = (
            "Use web search to answer with the most recent verifiable information.\n"
            "Answer in Korean unless the user asks otherwise.\n"
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
            for url in re.findall(r"https?://[^\s)\]>]+", answer):
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

        target_years = self._extract_target_years(text_query)
        now_intent = self._has_now_intent(text_query)
        public_office_query = self._is_public_office_query(text_query)
        if target_years and answer:
            trusted_links = [url for url in links if self._is_trusted_fresh_source(url)]
            if trusted_links:
                links = trusted_links
        if public_office_query:
            trusted_links = [url for url in links if self._is_trusted_fresh_source(url)]
            if trusted_links:
                links = trusted_links

        return answer, links

    def _sanitize_response_text(self, text: str) -> str:
        patterns = [
            r"(?im)^\s*\*{0,2}\s*(?:[-*]|\d+[.)])?\s*(?:summary|details|next\s*steps?)\s*\*{0,2}\s*:?\s*$",
        ]
        sanitized = text
        for pattern in patterns:
            sanitized = re.sub(pattern, "", sanitized)
        return re.sub(r"\n{3,}", "\n\n", sanitized).strip()

    def _friendly_connection_error(self, error_msg: str) -> str:
        message = (error_msg or "").lower()
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
        prefer_openai_web: bool = False,
    ) -> Tuple[str, str, bool]:
        self._last_web_error = ""
        detected_emotion = self._detect_emotion(text_query)
        fresh_required = self._needs_fresh_data(text_query)
        auto_web = self._should_use_web_search(text_query)
        force_web = use_web_search or auto_web
        web = (
            self._web_context(
                session_id,
                text_query,
                max_results=self.web_max_results,
                fresh_required=fresh_required,
                prefer_openai_web=prefer_openai_web,
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
        empathy_level: str = "balanced",
        session_id: str = "",
    ):
        provider = (provider or "openai").lower()
        session_key = self._session_key(session_id)
        sources: List[str] = []
        warning_banner = self._high_risk_warning(text_query)
        if warning_banner:
            yield f"{warning_banner}\n\n"
        direct_company_answer = self._direct_company_answer(text_query)
        if direct_company_answer:
            self._remember(session_key, "user", text_query)
            self._remember(session_key, "assistant", direct_company_answer)
            yield direct_company_answer
            return
        direct_knowledge_answer = self._direct_knowledge_answer(text_query)
        if direct_knowledge_answer:
            self._remember(session_key, "user", text_query)
            self._remember(session_key, "assistant", direct_knowledge_answer)
            yield direct_knowledge_answer
            return

        fresh_required = self._needs_fresh_data(text_query)
        now_intent = self._has_now_intent(text_query)
        direct_cache_key = self._normalize_search_query(self._build_web_query(text_query, fresh_required))
        skip_repeated_openai_web = True

        if fresh_required:
            cached_answer, cached_links = self._get_cached_answer(direct_cache_key)
            if not now_intent and cached_answer:
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
        web, detected_emotion, fresh_required = self._prepare_context(
            session_key,
            text_query,
            use_web_search,
            prefer_openai_web=not skip_repeated_openai_web,
        )
        sources = self._extract_sources(web) if web else []

        prompt = self._build_prompt(
            text_query=text_query,
            memory=memory,
            knowledge=knowledge,
            web=web,
            fresh_required=fresh_required,
            empathy_level=empathy_level,
            detected_emotion=detected_emotion,
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
            source_block = "\n\n[Sources]\n" + "\n".join(f"- {url}" for url in sources)
            yield source_block
            final_answer = f"{final_answer}{source_block}"
        if final_answer:
            self._remember(session_key, "assistant", final_answer)


agent_instance = CSAgent()
