# Final Project RSS Architecture Overview

## 1) Deployment Structure (Docker Compose)

```mermaid
flowchart LR
    user[User Browser]

    subgraph HOST[Linux Host]
        subgraph WEB[webserver container: nginx]
            https[HTTPS 40943 -> 443]
            http[HTTP 40916 -> 80]
            static[Static UI
            nginx/html]
            proxy[Reverse Proxy
            /api/* -> server_api:8000]
        end

        subgraph API[server_api container]
            app[FastAPI App
            /api/v1/*]
            modules[Modules
            auth / vision / llm / db / report]
        end

        subgraph DB[postgres container]
            pg[(PostgreSQL
            40919 -> 5432)]
        end

        subgraph CACHE[redis container]
            redis[(Redis
            40917 -> 6379)]
        end
    end

    user -->|Open UI| https
    user -->|Fallback/legacy| http
    https --> static
    https --> proxy
    proxy --> app
    app --> modules
    modules --> pg
    modules --> redis
```

## 2) Face ID Login Request Path

```mermaid
sequenceDiagram
    participant B as Browser (login.html)
    participant N as Nginx (webserver)
    participant A as server_api (/api/v1/auth)
    participant V as Face Engine (auth/vision)
    participant P as PostgreSQL

    B->>B: Capture frame from camera
    B->>N: POST /api/v1/auth/login/face
    N->>A: Proxy request
    A->>V: extract_face_embedding(image_base64)
    V-->>A: face embedding
    A->>P: Compare with face_embedding table
    P-->>A: match / no match
    A-->>N: 200 / 401 / 404 / 422 / 503
    N-->>B: Response
    B->>B: Show status message or redirect /auto.html
```

## 3) Port Map

- `40943`: Nginx HTTPS (recommended entry)
- `40916`: Nginx HTTP
- `40918`: server_api direct access
- `40919`: PostgreSQL
- `40917`: Redis
