from fastapi import FastAPI

app = FastAPI(title="Atlas API")


@app.get("/api/health")
def health():
    return {"status": "ok"}
