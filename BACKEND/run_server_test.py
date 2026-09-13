import sys
import uvicorn

print("SERVER PYTHON:", sys.executable, flush=True)

uvicorn.run(
    "main:app",
    host="127.0.0.1",
    port=8000,
    reload=False,
    workers=1,
)
