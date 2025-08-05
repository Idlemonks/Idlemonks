from jose import TWTError, jwt

SECRET_KEY = "secret123"   # where do i get the secret key?
ALGORITHM = "HS256"

def create_token(user_id):
    return jwt.encode ({"sub": user_id}, SECRET_KEY, alogrithms=ALGORITHM)

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithm = [ALGORITHM])
        return payload ["sub"]
    except JWTError:
        return None
