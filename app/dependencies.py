
import logging
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.todo import Todo

async def get_todo_or_404(db: AsyncSession, todo_id: int, owner_id: int) -> Todo:
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.owner_id == owner_id)
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    return todo

logger = logging.getLogger(__name__)
