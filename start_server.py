import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import uvicorn

PORT = int(os.environ.get("PORT", os.environ.get("SERVER_PORT", "8080")))
HOST = os.environ.get("HOST", "0.0.0.0")

if __name__ == "__main__":
    uvicorn.run("api.app:app", host=HOST, port=PORT)
