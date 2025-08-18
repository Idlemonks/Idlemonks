import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/ping")

@router.get("/ping-go")
def ping_go_service():
    try:
        response = requests.get("http://go_service:8081/ping")
        response.raise_for_status()
        return {"message": response.text}
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))