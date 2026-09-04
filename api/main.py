from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import documents, eval_routes, health, judge, query, ratings
from rag.tracing import configure_logging

load_dotenv()
configure_logging()

app = FastAPI(title="Simple RAG API")

# Local single-user dev tool: the `requests` calls from app.py/pages/*.py
# happen server-side (Streamlit's Python process calling this API directly),
# so cross-origin isn't actually in play for that traffic -- this is just
# cheap insurance for anyone opening this API's own /docs in a browser tab.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(judge.router)
app.include_router(ratings.router)
app.include_router(eval_routes.router)
