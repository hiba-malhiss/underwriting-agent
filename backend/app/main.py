from fastapi import FastAPI

app = FastAPI(title="Health Insurance Underwriting Agent")


@app.get("/health")
async def health():
    return {"status": "ok"}
