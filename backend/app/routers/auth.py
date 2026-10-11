"""认证路由：注册 / 登录 / 当前用户。

D2 验收标准（TODO.md）：
- 注册→登录→拿 token→/auth/me 返回用户名
- 库里密码是 $2b$...（security.hash_password）
- token 篡改返回 401（deps.get_current_user）
"""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenData, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter()


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="用户注册")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"code": 409, "msg": "用户名已存在", "data": None},
        )
    user = User(username=body.username, password=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"code": 201, "msg": "注册成功", "data": UserOut.model_validate(user).model_dump()}


@router.post("/login", summary="用户登录")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    # 用户名不存在与密码错误返回同一提示，避免账号枚举
    if user is None or not verify_password(body.password, user.password):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"code": 401, "msg": "用户名或密码错误", "data": None},
        )
    if user.status != 1:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"code": 403, "msg": "账号已被禁用", "data": None},
        )
    token = create_access_token(user.username)
    return {"code": 200, "msg": "ok", "data": TokenData(token=token, role=user.role).model_dump()}


@router.get("/me", summary="当前用户信息")
def me(current: User = Depends(get_current_user)):
    return {"code": 200, "msg": "ok", "data": UserOut.model_validate(current).model_dump()}
