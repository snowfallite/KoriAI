"""Accounts and sessions (tech.md §6.2)."""

from fastapi import APIRouter, Request, Response

from app.contracts.api.auth import LoginIn, MeOut, PasswordChangeIn, RegisterIn, UserOut
from app.domains.auth.deps import AuthServiceDep
from app.http.deps import CurrentUser, client_ip, session_cookie

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(
    body: RegisterIn, request: Request, response: Response, auth: AuthServiceDep
) -> UserOut:
    user, token = await auth.register(body, client_ip(request), request.headers.get("user-agent"))
    response.headers.append("set-cookie", session_cookie(token, request.app.state.settings))
    return user


@router.post("/login")
async def login(
    body: LoginIn, request: Request, response: Response, auth: AuthServiceDep
) -> UserOut:
    user, token = await auth.login(body, client_ip(request), request.headers.get("user-agent"))
    response.headers.append("set-cookie", session_cookie(token, request.app.state.settings))
    return user


@router.post("/logout", status_code=204)
async def logout(
    user: CurrentUser, request: Request, response: Response, auth: AuthServiceDep
) -> None:
    await auth.logout(user, client_ip(request))
    response.headers.append("set-cookie", session_cookie("", request.app.state.settings))


@router.post("/logout-all", status_code=204)
async def logout_all(
    user: CurrentUser, request: Request, response: Response, auth: AuthServiceDep
) -> None:
    await auth.logout_all(user, client_ip(request))
    response.headers.append("set-cookie", session_cookie("", request.app.state.settings))


@router.get("/me")
async def me(user: CurrentUser, auth: AuthServiceDep) -> MeOut:
    return await auth.me(user)


@router.post("/password", status_code=204)
async def change_password(
    body: PasswordChangeIn, user: CurrentUser, request: Request, auth: AuthServiceDep
) -> None:
    await auth.change_password(user, body, client_ip(request))
