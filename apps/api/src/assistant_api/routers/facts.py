"""Profile facts CRUD (EPIC-003 B2).

Facts feed the agent's ALLOWED FACTS prompt block and the policy engine's
disclose_fact allowlist. Writes are audited - facts are personal data
(AGENTS.md safety rules).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assistant_db.models import ProfileFact, User
from assistant_shared.schemas import Actor, ProfileFactCreate, ProfileFactOut

from ..audit import write_audit
from ..deps import get_default_user, get_session

router = APIRouter(prefix="/facts", tags=["facts"])


@router.get("", response_model=list[ProfileFactOut])
async def list_facts(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
) -> list[ProfileFact]:
    rows = (
        await session.execute(
            select(ProfileFact).where(ProfileFact.user_id == user.id).order_by(ProfileFact.key)
        )
    ).scalars()
    return list(rows)


@router.post("", response_model=ProfileFactOut)
async def upsert_fact(
    payload: ProfileFactCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
) -> ProfileFact:
    fact = (
        await session.execute(
            select(ProfileFact).where(
                ProfileFact.user_id == user.id, ProfileFact.key == payload.key
            )
        )
    ).scalar_one_or_none()
    created = fact is None
    if fact is None:
        fact = ProfileFact(user_id=user.id, key=payload.key)
        session.add(fact)
    fact.value = payload.value
    fact.sensitivity = payload.sensitivity
    fact.allowed_by_default = payload.allowed_by_default
    fact.allowed_scenarios = payload.allowed_scenarios
    # Audit without the value itself: fact values are sensitive.
    write_audit(
        session,
        user_id=user.id,
        actor=Actor.user,
        event_type="fact.created" if created else "fact.updated",
        payload={
            "key": payload.key,
            "sensitivity": payload.sensitivity,
            "allowed_by_default": payload.allowed_by_default,
            "allowed_scenarios": payload.allowed_scenarios,
        },
    )
    await session.commit()
    await session.refresh(fact)
    return fact


@router.delete("/{key}", status_code=204)
async def delete_fact(
    key: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_default_user),
) -> None:
    fact = (
        await session.execute(
            select(ProfileFact).where(ProfileFact.user_id == user.id, ProfileFact.key == key)
        )
    ).scalar_one_or_none()
    if fact is None:
        raise HTTPException(status_code=404, detail="fact not found")
    await session.delete(fact)
    write_audit(
        session,
        user_id=user.id,
        actor=Actor.user,
        event_type="fact.deleted",
        payload={"key": key},
    )
    await session.commit()
