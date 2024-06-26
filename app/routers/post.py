from ..database import get_db
from .. import models
from ..schemas import PostCreate, PostResponse, Post
from ..oauth2 import get_current_user

from fastapi import Response, status, HTTPException, Depends, APIRouter
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload, aliased
from sqlalchemy import func


router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("/sqlalchemy")
def test_posts(db: Session = Depends(get_db)):
    return {"status": "success"}


@router.get("/", response_model=List[PostResponse])
async def get_posts(
    db: Session = Depends(get_db),
    limit: int = None,
    offset: int = 0,
    search: Optional[str] = "",
):

    subquery = (
        db.query(models.Post, func.count(models.Vote.post_id).label("votes"))
        .outerjoin(models.Vote, models.Post.id == models.Vote.post_id)
        .group_by(models.Post.id)
        .filter(models.Post.title.contains(search))
        .limit(limit)
        .offset(offset)
        .subquery()
    )

    post_query = db.query(
        subquery.c,
        func.concat(models.User.first_name, " ", models.User.last_name).label(
            "author_name"
        ),
    ).join(models.User, subquery.c.author_id == models.User.id)

    posts = post_query.all()

    return posts


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Session = Depends(get_db)):
    subquery = (
        db.query(models.Post, func.count(models.Vote.post_id).label("votes"))
        .outerjoin(models.Vote, models.Post.id == models.Vote.post_id)
        .group_by(models.Post.id)
        .filter(models.Post.id == post_id)
        .subquery()
    )

    post_query = (
        db.query(
            subquery.c,
            func.concat(models.User.first_name, " ", models.User.last_name).label(
                "author_name"
            ),
        )
        .join(models.User, subquery.c.author_id == models.User.id)
        .order_by(subquery.c.id.asc())
    )

    post = post_query.first()

    if not post:
        raise HTTPException(
            status_code=404, detail=f"Post with ID {post_id} not found."
        )
    return post


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=Post)
async def create_post(
    body: PostCreate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    author_id = current_user.user_id
    new_post = models.Post(author_id=author_id, **body.model_dump())
    db.add(new_post)
    db.commit()
    db.refresh(new_post)

    return new_post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    post_query = db.query(models.Post).filter(models.Post.id == post_id)
    post = post_query.first()

    if post == None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found.",
        )
    
    if post.author_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform requested action",
        )

    post_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{post_id}", response_model=Post)
def update_post(
    post_id: int,
    body: PostCreate,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    post_query = db.query(models.Post).filter(models.Post.id == post_id)
    post = post_query.first()

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found.",
        )

    if post.author_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to perform requested action",
        )

    post_query.update(body.model_dump())
    db.commit()

    return post_query.first()
