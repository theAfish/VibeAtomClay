from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .routers import agent, files, logs, config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AtomClay Backend", description="Middle-layer API for connecting AtomClay frontend to Agentom server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agent.router)
app.include_router(files.router)
app.include_router(logs.router)
app.include_router(config.router)

@app.get("/")
async def root():
    return {"message": "AtomClay Middleware is running"}
