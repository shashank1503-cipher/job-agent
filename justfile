search refresh="":
    uv run python main.py {{ if refresh != "" { "--refresh" } else { "" } }}

mock:
    uv run python main.py --mock

parse-resume RESUME_PATH:
    uv run python utils/resume_parser.py {{RESUME_PATH}}

api:
    uv run uvicorn api.main:app --reload --port 8000

ui:
    cd frontend && npm run dev

dev:
    just api & just ui
