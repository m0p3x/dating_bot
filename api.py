import os
from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot
from bot.config import settings
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import aiohttp
from sqlalchemy import select, func, and_, not_, exists, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.config import settings
from bot.database import AsyncSessionFactory
from bot.models import User, UserTag, Tag, Like, Viewed, Event, EventCategory
from bot.services.profile_service import ProfileService
from bot.services.search_service import SearchService
from bot.services.match_service import MatchService
from bot.services.event_service import EventService
from bot.services.stats_service import StatsService
from bot.services.referral_service import ReferralService
from bot.services.premium_service import PremiumService

bot = Bot(token=settings.BOT_TOKEN)


app = FastAPI(title="GAZ Dating API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://gazdatingbot.ru", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_db() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session


class LikeRequest(BaseModel):
    from_user_id: int
    to_user_id: int
    type: str = "like"
    message: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height: Optional[int] = None
    city: Optional[str] = None
    goal: Optional[str] = None
    bio: Optional[str] = None
    interests: Optional[List[str]] = None


class EventCreate(BaseModel):
    category_id: int
    event_date: date
    description: str


# -------------------------------------------------------------------
# Эндпоинты
# -------------------------------------------------------------------
@app.get("/api/me")
async def get_me(tg_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "tg_id": user.tg_id,
        "name": user.name,
        "age": user.age,
        "gender": user.gender,
        "height": user.height,
        "city": user.city,
        "goal": user.goal,
        "bio": user.bio,
        "is_active": user.is_active,
        "is_banned": user.is_banned,
        "is_verified": user.is_verified,
        "has_premium": user.has_premium,
        "views_count": user.views_count,
        "photos": [{"file_id": p.file_id, "type": p.media_type, "order": p.order} for p in user.photos],
        "tags": [ut.tag.name for ut in user.tags if ut.tag],
    }


@app.get("/api/feed")
async def get_feed(
        tg_id: int,
        limit: int = 10,
        offset: int = 0,
        gender: str = "any",
        search_goal: str = None,
        search_interests: str = None,
        apply_height: bool = False,
        search_height: int = None,
        db: AsyncSession = Depends(get_db)
):
    svc = ProfileService(db)
    viewer = await svc.get_by_tg_id(tg_id)
    if not viewer:
        raise HTTPException(status_code=404, detail="User not found")

    search_svc = SearchService(db)
    search_gender = None if gender in ["any", "all", ""] else gender
    search_interests_list = [i.strip() for i in search_interests.split(",") if i.strip()] if search_interests else []

    profiles = []
    for _ in range(limit):
        # 1. Сначала ищем анкеты ТОЛЬКО в городе пользователя
        candidate = await search_svc.get_next_profile(
            viewer=viewer,
            search_gender=search_gender,
            search_goal=search_goal,
            search_interests=search_interests_list,
            apply_height=apply_height,
            search_height=search_height,
            ignore_city=False,  # ← только свой город
        )

        # 2. Если в своём городе не нашлось — ищем по ВСЕМ городам
        if not candidate:
            candidate = await search_svc.get_next_profile(
                viewer=viewer,
                search_gender=search_gender,
                search_goal=search_goal,
                search_interests=search_interests_list,
                apply_height=apply_height,
                search_height=search_height,
                ignore_city=True,  # ← расширяем поиск на все города
            )

        if not candidate:
            break

        await db.refresh(candidate, attribute_names=['photos', 'tags'])
        profiles.append(candidate)

    items = []
    for u in profiles:
        items.append({
            "id": u.id,
            "tg_id": u.tg_id,
            "name": u.name,
            "age": u.age,
            "gender": u.gender,
            "height": u.height,
            "city": u.city,
            "goal": u.goal,
            "bio": u.bio,
            "is_verified": u.is_verified,
            "has_premium": u.has_premium,
            "photos": [{"file_id": p.file_id, "type": p.media_type} for p in u.photos],
            "tags": [ut.tag.name for ut in u.tags if ut.tag],
        })
    return {"profiles": items, "has_more": len(items) == limit}


# Кэш для путей к файлам
file_path_cache = {}


async def get_file_path(bot_token: str, file_id: str) -> str:
    if file_id in file_path_cache:
        return file_path_cache[file_id]

    url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get("ok"):
                file_path = data["result"]["file_path"]
                file_path_cache[file_id] = file_path
                return file_path
    return None


@app.get("/api/photo/{file_id}")
async def get_photo(file_id: str):
    bot_token = settings.BOT_TOKEN
    file_path = await get_file_path(bot_token, file_id)
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    return RedirectResponse(url=file_url)


# стало
@app.post("/api/like")
async def send_like(data: LikeRequest, db: AsyncSession = Depends(get_db)):

    from bot.models import Match

    profile_svc = ProfileService(db)
    from_user = await profile_svc.get_by_tg_id(data.from_user_id)
    to_user = await profile_svc.get_by_tg_id(data.to_user_id)

    if not from_user or not to_user:
        print("DEBUG user not found, returning 404")
        raise HTTPException(status_code=404, detail="User not found")

    existing_match = await db.execute(
        select(Match).where(
            ((Match.user1_id == from_user.id) & (Match.user2_id == to_user.id)) |
            ((Match.user1_id == to_user.id) & (Match.user2_id == from_user.id))
        )
    )
    if existing_match.scalar_one_or_none():
        print("DEBUG already_match, returning early")
        return {"success": False, "already_match": True, "is_match": False}

    print("DEBUG calling match_svc.send_like")
    match_svc = MatchService(session=db, bot=bot)
    result = await match_svc.send_like(
        from_user=from_user,
        to_user=to_user,
        like_type=data.type,
        message=data.message,
    )

    if result == "limit":
        return {"success": False, "is_match": False, "limit_reached": True}
    if result is None:
        return {"success": True, "is_match": True}

    return {"success": True, "is_match": False}

@app.post("/api/viewed/{target_id}")
async def mark_profile_viewed(target_id: int, tg_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    viewer = await svc.get_by_tg_id(tg_id)
    if not viewer:
        raise HTTPException(status_code=404)
    search_svc = SearchService(db)
    await search_svc.mark_viewed(viewer.id, target_id)
    return {"success": True}

@app.get("/api/matches")
async def get_matches(tg_id: int, db: AsyncSession = Depends(get_db)):
    from bot.models import Match

    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(Match, User)
        .join(User, (User.id == Match.user2_id) | (User.id == Match.user1_id))
        .where(or_(Match.user1_id == user.id, Match.user2_id == user.id), User.id != user.id)
        .options(
            selectinload(User.photos),
            selectinload(User.tags).selectinload(UserTag.tag)
        )
    )
    rows = result.all()

    items = []
    for match, partner in rows:
        items.append({
            "user": {
                "id": partner.id,
                "tg_id": partner.tg_id,
                "username": partner.username,
                "name": partner.name,
                "age": partner.age,
                "city": partner.city,
                "is_verified": partner.is_verified,
                "photos": [{"file_id": p.file_id, "type": p.media_type} for p in partner.photos],
                "tags": [ut.tag.name for ut in partner.tags if ut.tag],
            },
            "matched_at": match.created_at.isoformat()
        })
    return {"matches": items}


@app.post("/api/undo_skip")
async def undo_skip(tg_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.has_premium:
        raise HTTPException(status_code=403, detail="Premium required")

    result = await db.execute(
        select(Viewed)
        .where(Viewed.viewer_id == user.id)
        .order_by(Viewed.created_at.desc())
        .limit(1)
    )
    last_viewed = result.scalar_one_or_none()
    if not last_viewed:
        raise HTTPException(status_code=404, detail="No previous profile")

    viewed_id = last_viewed.viewed_id  # ← Сохраняем ID

    await db.delete(last_viewed)
    await db.commit()

    return {"success": True, "profile_id": viewed_id}  # ← Возвращаем ID


@app.get("/api/incoming_likes")
async def incoming_likes(tg_id: int, db: AsyncSession = Depends(get_db)):
    profile_svc = ProfileService(db)
    user = await profile_svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    match_svc = MatchService(db, bot)
    likes = await match_svc.get_incoming_likes(user.id)
    result = []
    for like in likes:
        u = like.from_user
        result.append({
            "like_id": like.id,
            "user": {
                "id": u.id,
                "tg_id": u.tg_id,
                "name": u.name,
                "age": u.age,
                "city": u.city,
                "is_verified": u.is_verified,
                "photos": [{"file_id": p.file_id, "type": p.media_type} for p in u.photos],
            },
            "type": like.type,
            "message": like.message,
        })
    return {"likes": result}


@app.post("/api/reply_like")
async def reply_like(like_id: int, tg_id: int, db: AsyncSession = Depends(get_db)):
    profile_svc = ProfileService(db)
    user = await profile_svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    match_svc = MatchService(db, bot)
    matched = await match_svc.reply_like(like_id, user)
    return {"success": matched}


@app.delete("/api/incoming_likes/{like_id}")
async def delete_incoming_like(like_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Like).where(Like.id == like_id))
    like = result.scalar_one_or_none()
    if not like:
        raise HTTPException(status_code=404, detail="Like not found")
    await db.delete(like)
    await db.commit()
    return {"success": True}


@app.get("/api/profile/{target_tg_id}")
async def get_profile(
        target_tg_id: int,
        tg_id: int = None,
        db: AsyncSession = Depends(get_db)
):
    svc = ProfileService(db)
    target_user = await svc.get_by_tg_id(target_tg_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    is_mutual = False
    if tg_id:
        current_user = await svc.get_by_tg_id(tg_id)
        if current_user:
            result = await db.execute(
                select(Like).where(
                    Like.from_id == current_user.id,
                    Like.to_id == target_user.id,
                    Like.is_mutual == True
                )
            )
            is_mutual = result.scalar_one_or_none() is not None
            if not is_mutual:
                result = await db.execute(
                    select(Like).where(
                        Like.from_id == target_user.id,
                        Like.to_id == current_user.id,
                        Like.is_mutual == True
                    )
                )
                is_mutual = result.scalar_one_or_none() is not None

    return {
        "id": target_user.id,
        "tg_id": target_user.tg_id,
        "username": target_user.username,
        "name": target_user.name,
        "age": target_user.age,
        "gender": target_user.gender,
        "height": target_user.height,
        "city": target_user.city,
        "goal": target_user.goal,
        "bio": target_user.bio,
        "is_verified": target_user.is_verified,
        "has_premium": target_user.has_premium,
        "photos": [{"file_id": p.file_id, "type": p.media_type} for p in target_user.photos],
        "tags": [ut.tag.name for ut in target_user.tags if ut.tag],
        "is_mutual": is_mutual,
    }


@app.put("/api/profile")
async def update_profile(tg_id: int, data: ProfileUpdate, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.name is not None:
        user.name = data.name
    if data.age is not None:
        user.age = data.age
    if data.gender is not None:
        user.gender = data.gender
    if data.height is not None:
        user.height = data.height
    if data.city is not None:
        user.city = data.city
    if data.goal is not None:
        user.goal = data.goal
    if data.bio is not None:
        user.bio = data.bio
    if data.interests is not None:
        await svc.set_tags(user.id, data.interests)
    await db.commit()
    return {"success": True}


@app.get("/api/events/categories")
async def event_categories(db: AsyncSession = Depends(get_db)):
    svc = EventService(db)
    cats = await svc.get_categories()
    return [{"id": c.id, "name": c.name, "emoji": c.emoji} for c in cats]


@app.get("/api/events")
async def get_events(tg_id: int, category_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user or not user.city:
        return {"events": []}
    event_svc = EventService(db)
    if category_id:
        events = await event_svc.get_events_by_category(category_id, user.city)
    else:
        cats = await event_svc.get_categories()
        events = []
        for cat in cats:
            evs = await event_svc.get_events_by_category(cat.id, user.city)
            events.extend(evs)
        events.sort(key=lambda x: x.event_date)
    result = []
    for ev in events:
        result.append({
            "id": ev.id,
            "creator_id": ev.creator_id,
            "category_id": ev.category_id,
            "event_date": ev.event_date.isoformat(),
            "description": ev.description,
            "participants_count": len(ev.participants) if ev.participants else 0,
        })
    return {"events": result}


@app.post("/api/events")
async def create_event(tg_id: int, data: EventCreate, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user or not user.city:
        raise HTTPException(status_code=400, detail="City not set")
    event_svc = EventService(db)
    event = await event_svc.create_event(
        creator_id=user.id,
        category_id=data.category_id,
        city=user.city,
        event_date=data.event_date,
        description=data.description,
    )
    return {"id": event.id, "success": True}


@app.delete("/api/events/{event_id}")
async def cancel_event(event_id: int, tg_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    event_svc = EventService(db)
    event = await event_svc.get_event_by_id(event_id)
    if not event or event.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    event.is_active = False
    await db.commit()
    return {"success": True}


@app.get("/api/stats")
async def get_stats(tg_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404)

    likes_received = await db.execute(
        select(func.count()).where(Like.to_id == user.id)
    )
    likes_received = likes_received.scalar_one() or 0

    likes_sent = await db.execute(
        select(func.count()).where(Like.from_id == user.id)
    )
    likes_sent = likes_sent.scalar_one() or 0

    profiles_viewed = await db.execute(
        select(func.count()).where(Viewed.viewer_id == user.id)
    )
    profiles_viewed = profiles_viewed.scalar_one() or 0

    views_count = user.views_count or 0

    rank_result = await db.execute(
        select(func.count()).select_from(
            select(User.id).join(Like, Like.to_id == User.id)
            .group_by(User.id)
            .having(func.count(Like.id) > likes_received)
            .subquery()
        )
    )
    rank = rank_result.scalar_one() + 1 if likes_received > 0 else 1

    return {
        "likes_received": likes_received,
        "likes_sent": likes_sent,
        "profiles_viewed": profiles_viewed,
        "views_count": views_count,
        "rank": rank
    }


@app.get("/api/referral")
async def referral_info(tg_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404)
    ref_svc = ReferralService(db)
    link = await ref_svc.generate_referral_link(user.id)
    stats = await ref_svc.get_referral_stats(user.id)
    return {"link": link, "total": stats["total"], "activated": stats["activated"], "bonus_hours": stats["bonus_hours"]}


@app.get("/api/top5")
async def top5(db: AsyncSession = Depends(get_db)):
    stats_svc = StatsService(db)
    rows = await stats_svc.get_top5()
    result = []
    for user, likes_count in rows:
        result.append({
            "name": user.name,
            "age": user.age,
            "city": user.city,
            "likes_count": likes_count,
            "photos": [{"file_id": p.file_id, "type": p.media_type} for p in user.photos],
        })
    return {"top5": result}


@app.get("/api/premium/status")
async def premium_status(tg_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProfileService(db)
    user = await svc.get_by_tg_id(tg_id)
    if not user:
        raise HTTPException(status_code=404)
    premium_svc = PremiumService(db)
    has = await premium_svc.check_and_expire(user)
    return {"has_premium": has, "premium_until": user.premium_until.isoformat() if user.premium_until else None}


@app.get("/api/profile_by_id/{profile_id}")
async def get_profile_by_id(
        profile_id: int,
        tg_id: int,
        db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select
    from bot.models import User

    svc = ProfileService(db)
    current_user = await svc.get_by_tg_id(tg_id)
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(User)
        .where(User.id == profile_id)
        .options(
            selectinload(User.photos),
            selectinload(User.tags).selectinload(UserTag.tag)
        )
    )
    target_user = result.scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id": target_user.id,
        "tg_id": target_user.tg_id,
        "username": target_user.username,
        "name": target_user.name,
        "age": target_user.age,
        "gender": target_user.gender,
        "height": target_user.height,
        "city": target_user.city,
        "goal": target_user.goal,
        "bio": target_user.bio,
        "is_verified": target_user.is_verified,
        "has_premium": target_user.has_premium,
        "photos": [{"file_id": p.file_id, "type": p.media_type} for p in target_user.photos],
        "tags": [ut.tag.name for ut in target_user.tags if ut.tag],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)