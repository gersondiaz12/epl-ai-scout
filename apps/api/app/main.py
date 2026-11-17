from fastapi import FastAPI

from app.routers import clubs, in_form, players, seasons

app = FastAPI(title="EPL AI Scout API")
app.include_router(seasons.router)
app.include_router(clubs.router)
app.include_router(players.router)
app.include_router(in_form.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
