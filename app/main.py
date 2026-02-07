import sqlite3
from datetime import datetime
import os
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
        conn.execute("PRAGMA journal_mode=WAL") # 开启 WAL 模式优化并发
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, action TEXT NOT NULL, ip_address TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
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
async def handle_login(request: Request, username: str = Form(...), password: str = Form(...)):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        
        if user and pwd_context.verify(password, user[0]):
            add_audit_log(username, "登录成功", request)
            request.session["user"] = username
            return RedirectResponse(url="/", status_code=303)
        
    add_audit_log(username, f"登录失败", request)
    return RedirectResponse(url="/login?error=1", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # 检查 Session 是否存在
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url="/login")
    
    # 定义导航链接
    NAV_LINKS = [
        {"name": "文件传输柜", "url": "https://filebox.aedl.top", "icon": "🚀", "desc": "临时文件快传系统"},
        {"name": "资料库", "url": "https://cloud.aedl.top", "icon": "📂", "desc": "内部文件，切勿外传！"},
        {"name": "文章主页", "url": "https://www.aedl.top", "icon": "📃", "desc": "实验室文章主页"},
        {"name": "打印机状态", "url": "https://3Dprinter.aedl.top", "icon": "🔩", "desc": "查看3D打印机状态信息"},
        {"name": "Overleaf", "url": "https://www.overleaf.com", "icon": "📝", "desc": "在线 LaTeX 编辑与协作平台"},
        {"name": "StackEdit", "url": "https://stackedit.io/app#", "icon": "✍️", "desc": "在线 Markdown 编辑器"},
        {"name": "Diagrams.net", "url": "https://app.diagrams.net", "icon": "📊", "desc": "原 draw.io，流程图及架构图绘制工具"},
        {"name": "ADI Filter Wizard", "url": "https://tools.analog.com/en/filterwizard/", "icon": "⚡", "desc": "亚德诺半导体滤波器设计向导，支持幅频特性仿真"},
        {"name": "LCEDA Pro", "url": "https://pro.lceda.cn/editor", "icon": "📐", "desc": "立创EDA在线专业版"},
        {"name": "Falstad Circuit", "url": "https://www.falstad.com/circuit/", "icon": "⚡", "desc": "直观的在线电路物理模拟仿真器，支持电流动画"},
        {"name": "Wokwi", "url": "https://wokwi.com", "icon": "🤖", "desc": "Arduino、ESP32 等平台的在线嵌入式仿真平台"},
        {"name": "波特律动串口助手", "url": "https://serial.baud-dance.com/#/", "icon": "📟", "desc": "免安装浏览器串口调试工具"},
        {"name": "CyberChef", "url": "https://gchq.github.io/CyberChef/", "icon": "🍳", "desc": "“数据处理工具，涵盖加解密、进制转换等"},
        {"name": "半导小芯", "url": "https://www.semiee.com", "icon": "📖", "desc": "芯片 Datasheet 数据手册查询平台"},
        {"name": "WolframAlpha", "url": "https://www.wolframalpha.com", "icon": "🔢", "desc": "计算知识引擎，可用于解复杂的工程数学方程"},
        {"name": "JSON.cn", "url": "https://www.json.cn", "icon": "🗂️", "desc": "简洁明了的在线 JSON 解析、格式化与校验工具"},
        {"name": "Regex101", "url": "https://regex101.com", "icon": "🔍", "desc": "正则表达式在线测试、解释与调试利器"},
        {"name": "Mermaid Live", "url": "https://mermaid.live", "icon": "🧜‍♀️", "desc": "基于代码生成流程图、时序图的在线编辑器"}
    ]
    return templates.TemplateResponse("index.html", {"request": request, "links": NAV_LINKS, "username": user})

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

# 个人中心页面：显示修改密码的表单
@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    # 先检查有没有登录 Session
    username = request.session.get("user")
    if not username:
        return RedirectResponse(url="/login")
    # 渲染刚才创建的 profile.html 模板
    return templates.TemplateResponse("profile.html", {"request": request, "username": username})

# 处理修改密码逻辑
@app.post("/change-password")
async def handle_change_password(request: Request, old_pwd: str = Form(...), new_pwd: str = Form(...)):
    username = request.session.get("user")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        
        # 校验旧密码是否正确
        if user and pwd_context.verify(old_pwd, user[0]):
            new_h = pwd_context.hash(new_pwd) # 加密新密码
            conn.execute("UPDATE users SET password_hash=? WHERE username=?", (new_h, username))
            conn.commit()
            # 修改成功后记录日志并退出登录
            add_audit_log(username, "修改密码成功", request)
            return RedirectResponse(url="/logout", status_code=303)
            
    # 如果旧密码错了，跳回修改页并带上错误参数
    return RedirectResponse(url="/profile?error=1", status_code=303)