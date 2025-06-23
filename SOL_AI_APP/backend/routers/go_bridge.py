import requests

def ping_go_service():
    response = request.get("http://go_service:8081/ping")
    return response.text