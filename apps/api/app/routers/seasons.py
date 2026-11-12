from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.metrics import PER90_MIN_MINUTES
from app.queries import get_season
from app.schemas import SeasonOut

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("/current")
def current_season(session: Annotated[Session, Depends(get_session)]) -> SeasonOut:
    season = get_season(session, None)
    return SeasonOut(
        label=season.label,
        start_date=season.start_date,
        end_date=season.end_date,
        per90_min_minutes=PER90_MIN_MINUTES,
    )
