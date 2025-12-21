from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from .routers import agent, files, logs, config, materials
from .services import archive_workspace, cleanup_workspace

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic (if any)
    yield
    # Shutdown logic
    logger.info("Shutting down middleware...")
    cleanup_workspace()

app = FastAPI(
    title="AtomClay Backend", 
    description="Middle-layer API for connecting AtomClay frontend to Agentom server",
    lifespan=lifespan
)

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
app.include_router(materials.router)

@app.get("/")
async def root():
    return {"message": "AtomClay Middleware is running"}
