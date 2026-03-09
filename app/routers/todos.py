from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.todo import Todo
from app.schemas.todo import TodoCreate, TodoResponse, TodoUpdate, TodoWithOwner
from app.auth import get_current_user
from app.dependencies import get_todo_or_404

router = APIRouter(prefix="/todos", tags=["todos"])

@router.post("/", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_todo(todo: TodoCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    db_todo = Todo(**todo.model_dump(), owner_id=current_user.id)
    db.add(db_todo)
    await db.commit()
    await db.refresh(db_todo)
    return db_todo

@router.get("/", response_model=List[TodoResponse])
async def read_todos(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Todo).where(Todo.owner_id == current_user.id))
    return result.scalars().all()

@router.get("/{todo_id}", response_model=TodoWithOwner)
async def read_todo(todo_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    todo = await get_todo_or_404(db, todo_id, current_user.id.to_string())
    return todo

@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: int, todo_update: TodoUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    todo = await get_todo_or_404(db, todo_id, current_user.id.to_string())
    update_data = todo_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(todo, key, value)
    await db.commit()
    await db.refresh(todo)
    return todo

@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(todo_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    todo = await get_todo_or_404(db, todo_id, current_user.id.to_string())
    await db.delete(todo)
    await db.commit()
    return None