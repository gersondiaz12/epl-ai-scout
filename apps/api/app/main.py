from fastapi import FastAPI

app = FastAPI(title="EPL AI Scout API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
