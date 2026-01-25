from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()


@app.get("/api", response_class=PlainTextResponse)
def analyst() -> str:
    return "Analyst"
