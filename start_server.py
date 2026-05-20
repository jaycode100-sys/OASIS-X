import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import uvicorn
uvicorn.run("api.app:app", host="0.0.0.0", port=8080)
