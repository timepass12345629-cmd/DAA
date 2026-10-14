"""
RingScope API server entrypoint.
Run:   python run_server.py
       or
       uvicorn ringscope.api:app --reload --port 8000
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("ringscope.api:app", host="127.0.0.1", port=8000, reload=True)
