from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from server import settings

# setup basic http auth
security = HTTPBasic()


def authenticate(credentials: HTTPBasicCredentials = Depends(security)):

    if (settings.correct_username is None) or (settings.correct_password is None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Environment variables for authentication are not set",
        )
    if not (credentials.username == settings.correct_username and credentials.password == settings.correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials
