import sqlite3
from datetime import datetime
import os
import json
from fastapi import FastAPI, Request, Form, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv("SECRET_KEY", "fallback_secret_for_dev"),
    domain=".aedl.top",
    max_age=86400,
    same_site="lax",
    https_only=True
)
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DB_PATH = "data/users.db"

# --- 1. 数据库逻辑 ---
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        
        # 确保表存在
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                ip_address TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()

init_db()

def add_audit_log(username: str, action: str, request: Request):
    ip = request.headers.get("X-Forwarded-For", request.client.host)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO audit_logs (username, action, ip_address) VALUES (?, ?, ?)", (username, action, ip))
        conn.commit()

# --- 2. 路由逻辑 ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # 渲染登录页
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def handle_login(request: Request, login_id: str = Form(...), password: str = Form(...)): # 参数名改为 login_id
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # 支持通过 账号(account) 或 用户名(username) 登录
        cursor.execute("SELECT account, username, password_hash, role FROM users WHERE account=? OR username=?", (login_id, login_id))
        user_row = cursor.fetchone()
        
        if user_row and pwd_context.verify(password, user_row[2]):
            account, username, _, role = user_row
            add_audit_log(f"{username}({account})", "登录成功", request)
            request.session["user"] = account # session 存储唯一标识 account
            request.session["display_name"] = username # session 存储显示名
            request.session["role"] = role # session 存储角色
            return RedirectResponse(url="/", status_code=303)
        
    add_audit_log(login_id, f"登录失败", request)
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # 检查 Session 是否存在
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    # 定义导航链接
    # 加载导航链接
    try:
        with open("data/nav_links.json", "r", encoding="utf-8") as f:
            NAV_LINKS = json.load(f)
    except FileNotFoundError:
        NAV_LINKS = []  # 如果文件不存在，默认为空列表或者提供一些默认值
    
    # 加载问候语和一言
    try:
        with open("data/greetings.json", "r", encoding="utf-8") as f:
            greeting_data = json.load(f)
    except FileNotFoundError:
        greeting_data = {"greetings": {}, "hitokoto": []}

    # 获取显示名，如果session里没有（旧session），则回退到 user (account)
    display_name = request.session.get("display_name", user)
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "links": NAV_LINKS, 
        "username": display_name,
        "greetings": greeting_data.get("greetings", {}),
        "hitokoto_list": greeting_data.get("hitokoto", [])
    })

@app.get("/verify")
async def auth_verify(request: Request):
    """供 NPM 子域名验证使用"""
    # 验证 Session
    if request.session.get("user"):
        return Response(status_code=200)
    return Response(status_code=401)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

# 个人中心页面
@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    account = request.session.get("user")
    if not account:
        return RedirectResponse(url="/login")
        
    # 获取最新用户信息
    username = ""
    role = "user"
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, role FROM users WHERE account=?", (account,))
        row = cursor.fetchone()
        if row:
            username = row[0]
            role = row[1]

    # 更新 session 中的 display_name 以防不一致
    request.session["display_name"] = username
            
    return templates.TemplateResponse("profile.html", {
        "request": request, 
        "account": account, 
        "username": username,
        "role": role
    })

# 处理修改用户名逻辑
@app.post("/change-username")
async def handle_change_username(request: Request, new_username: str = Form(...)):
    account = request.session.get("user")
    if not account:
        return RedirectResponse(url="/login")

    # 验证用户名格式: 允许数字，大小写字母和下划线
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', new_username):
        return RedirectResponse(url="/profile?error_username=invalid_format", status_code=303)
        
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("UPDATE users SET username=? WHERE account=?", (new_username, account))
            conn.commit()
            request.session["display_name"] = new_username
            add_audit_log(f"{new_username}({account})", "修改用户名成功", request)
            return RedirectResponse(url="/profile?success_username=1", status_code=303)
        except sqlite3.IntegrityError:
            # 用户名被占用
            return RedirectResponse(url="/profile?error_username=taken", status_code=303)

# 处理修改密码逻辑
@app.post("/change-password")
async def handle_change_password(request: Request, old_pwd: str = Form(...), new_pwd: str = Form(...)):
    account = request.session.get("user")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, username FROM users WHERE account=?", (account,))
        user_row = cursor.fetchone()
        
        # 校验旧密码是否正确
        if user_row and pwd_context.verify(old_pwd, user_row[0]):
            new_h = pwd_context.hash(new_pwd) # 加密新密码
            conn.execute("UPDATE users SET password_hash=? WHERE account=?", (new_h, account))
            conn.commit()
            # 修改成功后记录日志并退出登录
            add_audit_log(f"{user_row[1]}({account})", "修改密码成功", request)
            return RedirectResponse(url="/logout", status_code=303)
            
    # 如果旧密码错了，跳回修改页并带上错误参数
    return RedirectResponse(url="/profile?error=1", status_code=303)