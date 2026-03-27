# Final Project RSS Module Architecture

요청하신 것처럼 "모듈 단위"로 바로 볼 수 있게 구성했습니다.

## 1) Backend Module Map (Code-Centric)

```mermaid
flowchart LR
    subgraph CLIENT["Client Layer (Nginx Static UI)"]
        login["login.html / js/login.js\nFace ID, Password Login"]
        auto["auto.html / js/dashboard.js\nDashboard + LLM UI"]
        config["configuration.html / iot.html\nOperations UI"]
    end

    subgraph API["server_api (FastAPI /api/v1)"]
        subgraph AUTH["auth module"]
            auth_router[router.py]
            auth_service[service.py]
            auth_jwt[jwt.py]
            auth_vision[vision/service.py]
            auth_db["db/model.py + db/schema.py"]
            auth_router --> auth_service
            auth_service --> auth_jwt
            auth_service --> auth_vision
            auth_service --> auth_db
        end

        subgraph VISION["vision module"]
            vision_router[router.py]
            vision_service[service.py]
            vision_db["db/model.py + db/crud.py + db/schema.py"]
            vision_router --> vision_service --> vision_db
        end

        subgraph LLM["llm module"]
            llm_router[router.py]
            llm_chat[llm_chat_api.py]
            llm_media[llm_media_api.py]
            llm_q["llm_question.py / llm_result_api.py"]
            llm_svc["services/openai_service.py\nservices/agent_service.py\nservices/knowledge_service.py"]
            llm_router --> llm_chat
            llm_router --> llm_media
            llm_router --> llm_q
            llm_chat --> llm_svc
            llm_media --> llm_svc
            llm_q --> llm_svc
        end

        subgraph REPORT["report module"]
            report_router[router.py]
            report_service["service.py / report.py"]
            report_db["db/model.py + db/crud.py + db/schema.py"]
            report_router --> report_service --> report_db
        end

        subgraph RAG["rag module"]
            rag_router[router.py]
            rag_service[service.py]
            rag_db["db/model.py + db/crud.py + db/schema.py"]
            rag_router --> rag_service --> rag_db
        end

        subgraph OPT["optimization module"]
            opt_router[router.py]
            opt_service[service.py]
            opt_schema[db/schema.py]
            opt_router --> opt_service --> opt_schema
        end

        subgraph VOICE["voice_interaction module"]
            voice_router[router.py]
            voice_service[service.py]
            voice_schema[db/schema.py]
            voice_router --> voice_service --> voice_schema
        end

        subgraph DASH["dashboard module"]
            dash_router[router.py]
            dash_service[service.py]
            dash_repo[repository.py]
            dash_schema[schemas.py]
            dash_router --> dash_service --> dash_repo
            dash_service --> dash_schema
        end

        subgraph COMMON["common module"]
            common_rbac[rbac.py]
            common_audit[audit.py]
        end
    end

    subgraph DATA["Data & Infra"]
        pg[(PostgreSQL)]
        redis[(Redis)]
        extai[(External AI APIs)]
    end

    login --> AUTH
    auto --> DASH
    auto --> LLM
    auto --> VISION
    config --> OPT
    config --> REPORT
    config --> RAG
    config --> VOICE

    AUTH --> pg
    VISION --> pg
    REPORT --> pg
    RAG --> pg
    DASH --> pg
    OPT --> pg
    VOICE --> pg

    LLM --> extai
    LLM --> redis
```

## 2) Face / Voice / Gesture Pipeline View (Operational)

```mermaid
flowchart LR
    cam_client["Client CAM Input"] --> ui_recog["User Recognition UI\nlogin.js / auto pages"]

    subgraph SERVER["Server Side Processing"]
        face["auth + auth/vision\nFace Embedding/Match"]
        voice["voice_interaction\nVoice Recognition Workflow"]
        gesture["vision\nGesture/Overlay Processing"]
        logger["common/audit + report\nLogging/Reporting"]
    end

    subgraph DBLAYER["Storage"]
        face_tbl[("face_embedding_table / vector_table")]
        user_tbl[(user_table)]
        log_tbl[("production/report tables")]
    end

    ui_recog -->|Face login request| face
    ui_recog -->|Voice related request| voice
    ui_recog -->|Vision frame/overlay| gesture

    face -->|Read/Write| face_tbl
    face -->|User check| user_tbl
    voice -->|User/Session info| user_tbl
    gesture -->|Event data| log_tbl

    face -->|Check-in/out decision| ui_recog
    voice -->|Command result| ui_recog
    gesture -->|Recognition result| ui_recog

    ui_recog -->|Send activity logs| logger
    logger -->|Persist| log_tbl
```

## 3) Module Responsibility Quick Table

| Module | Main Role | Key Files |
|---|---|---|
| `auth` | Password/Face 인증, JWT, 계정 상태 검사 | `router.py`, `service.py`, `jwt.py`, `vision/service.py` |
| `vision` | 카메라/오버레이/비전 데이터 처리 | `router.py`, `service.py`, `db/*` |
| `llm` | 채팅/미디어/질문/지식기반 LLM 처리 | `router.py`, `llm_*`, `services/*` |
| `dashboard` | KPI/대시보드 집계 API | `router.py`, `service.py`, `repository.py` |
| `report` | 리포트 생성/조회 | `router.py`, `service.py`, `report.py`, `db/*` |
| `rag` | RAG 관련 데이터/질의 | `router.py`, `service.py`, `db/*` |
| `optimization` | 최적화 관련 API | `router.py`, `service.py`, `db/schema.py` |
| `voice_interaction` | 음성 인터랙션 API | `router.py`, `service.py`, `db/schema.py` |
| `common` | 공통 RBAC/감사 유틸 | `rbac.py`, `audit.py` |
