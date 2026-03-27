from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import router as llm_v1_router


def _load_sample_env() -> None:
    sample_dir = Path(__file__).resolve().parent
    project_root_env = sample_dir.parents[4] / ".env"
    sample_env = sample_dir / ".env"

    for candidate in (project_root_env, sample_env):
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=False)


_load_sample_env()

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(llm_v1_router, prefix="/api/v1")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
