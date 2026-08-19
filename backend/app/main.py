from __future__ import annotations
import app.env  
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import analyze, health, price

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Market Pulse",
    description="Live market intelligence agent: cited news synthesis + price charts.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo/portfolio project; tighten for real deployment
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(analyze.router, tags=["analyze"])
app.include_router(price.router, tags=["price"])
