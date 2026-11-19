import os

from fastapi import FastAPI

app = FastAPI()
VERSION = os.getenv("APP_VERSION", "v1")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {"hello": VERSION}
