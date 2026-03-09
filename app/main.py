from fastapi import FastAPI
from app.routers import auth, users, todos

app = FastAPI(title="Todo API with Users", version="1.0.0")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(todos.router)

async def init_db():
    from app.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def on_startup():
    await init_db() 
    
@app.get("/")
async def root():
    return {"message": "Welcome to Todo API", "docs": "/docs"}