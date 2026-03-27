workspace "Final Project RSS - LLM Module" "C4 container view centered on the LLM module and its real code dependencies." {

    model {
        user = person "Operator / User" "Uses the dashboard chat, STT, TTS, and recommended questions."

        system = softwareSystem "Final Project RSS" "Nginx-served frontend with a FastAPI backend."

        frontend = container system "Web Frontend" "Static HTML + Vanilla JS" "Nginx served pages and dashboard.js"
        api = container system "FastAPI API" "Python / FastAPI" "src/main.py and src/api/v1/router.py"
        llmModule = container system "LLM Module" "Python package" "src/modules/llm"
        postgres = container system "PostgreSQL" "PostgreSQL" "Application database created at startup"

        knowledgeFolder = softwareSystem "Knowledge Folder" "LLM_KNOWLEDGE_PATH folder containing TXT, PDF, and image files."
        openai = softwareSystem "OpenAI APIs" "Chat, Responses Web Search, Audio, Image, Vision OCR, Embeddings"
        serper = softwareSystem "Serper" "Search API"
        tavily = softwareSystem "Tavily" "Search API"
        altProviders = softwareSystem "Optional LLM Providers" "Gemini and vLLM when configured"

        user -> frontend "Uses"
        frontend -> api "Calls /api/v1/* via Nginx reverse proxy"
        api -> llmModule "Mounts /api/v1/llm"
        api -> postgres "Creates tables and seeds admin on startup"

        frontend -> llmModule "Calls /api/v1/llm/chat, /tts, /stt, /recommended-questions"
        llmModule -> knowledgeFolder "Reads and writes uploaded knowledge files"
        llmModule -> openai "Uses chat, audio, image, vision OCR, embeddings, and responses web search"
        llmModule -> serper "Searches fresh web results"
        llmModule -> tavily "Searches fresh web results"
        llmModule -> altProviders "Uses optional Gemini / vLLM providers"
    }

    views {
        container system "llm-container" {
            include *
            autoLayout lr
            title "Final Project RSS - LLM Module Container Diagram"
            description "Real code-based container relationships centered on src/modules/llm."
        }

        theme default
    }
}
