"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routes.video_routes import router as video_router

app = FastAPI(
    title="AutoShorts AI",
    description="Automatically generate YouTube Shorts",
)

app.include_router(video_router)
