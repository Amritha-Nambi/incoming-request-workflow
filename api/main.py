from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from db.database import init_db
from routers import process, console


@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs once on startup so the cases table exists before any request hits it
    init_db()
    yield


app = FastAPI(title="Incoming Request Processing Workflow", lifespan=lifespan)
app.include_router(process.router, tags=["process"])
app.include_router(console.router, prefix="/console", tags=["console"])
