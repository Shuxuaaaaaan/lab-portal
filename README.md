# AEDL Online Workstation Portal

AEDL 在线工作站门户。为各工具提供统一的入口导航和身份认证服务。

## 简介

本项目是一个基于FastAPI开发的轻量级门户系统，通过统一的界面集成实验室内部工具（如文件传输、资料库）以及常用的工程开发工具（如仿真工具、文档协作平台）。同时，它提供了一套基于Session的统一身份认证机制，可用于保护后端服务。

本项目为作者初识容器、前后端与Git的入门项目，存在大量AI生成代码，不保证代码的稳定性，仅供学习参考。如您发现错误或有其他问题，请在Issues中提交；如您是实验室成员且发现网站直接炸了请直接通过邮箱或聊天软件提醒作者。感激不尽😭

## 主要功能

*   统一导航面板: 聚合了实验室内部工具和其他常用科研与工程工具。
*   安全认证:
    *   内置用户登录与会话管理。
    *   使用Bcrypt算法对密码进行安全哈希存储。
    *   提供 `/verify` 接口，可配合Nginx Proxy Manager (NPM)的 `Forward Auth` 功能，实现对其他子服务的统一鉴权保护。
*   CLI 管理控制台: 提供 `manage.py` 命令行工具，用于系统维护。
    *   用户管理: 增删查改用户信息。
    *   审计日志: 记录登录成功/失败、密码修改等关键操作，支持按条件筛选查询。
    *   服务控制：快速查看、重启、停止Docker服务容器。
*   个人中心: 支持用户自行修改密码。

## 技术栈

*   后端框架: Python FastAPI
*   数据库: SQLite
*   模板引擎: Jinja2
*   容器化: Docker & Docker Compose

## 待解决问题与更新方向

- [x] 账号信息单一，使用学号登录存在信息泄露风险。计划加入自定义用户名并支持用户名登录，学号仅用于校验和内部管理
- [ ] 完善日志系统，与其他功能模块的日志进行整合
- [ ] 设计Web端管理控制台，用于管理用户、服务、日志等
- [ ] 统一鉴权与filebrowser登录鉴权存在问题，需进一步完善
- [x] 导航链接写死在main.py内，需优化，计划加入独立的配置文件管理
- [ ] 安全性仍需验证

## 快速开始

### 部署运行
本项目推荐使用 Docker Compose 进行一键部署。
```bash
# 启动服务 (后台运行)
docker compose up -d
# 查看日志
docker compose logs -f
```
### 初始化与管理
项目自带一个简易的命令行管理工具 `manage.py`，用于审阅日志数据和管理用户。

**运行环境要求**:
*   Python 3.x
*   依赖库: `passlib`, `bcrypt`
**安装管理工具依赖**:

如果您在宿主机直接运行管理脚本，请先安装依赖：

```bash
pip install passlib bcrypt
```

**进入管理控制台**:

```bash
python manage.py
```

您将看到如下菜单，根据提示操作即可：

```text
===================================================
           Lab Portal 综合管理控制台
===================================================

[ 主菜单 ]
1. 用户管理  (添加初始用户、重置密码等)
2. 日志中心  (查看审计日志、系统实时日志)
3. 系统维护  (重启服务、查看状态)
0. 退出
```

> 注意: 首次启动前，建议先通过 `python manage.py` 添加一个管理员用户，否则无法登录系统。

## 目录结构说明

```text
.
├── app/
│   ├── main.py          # FastAPI 主程序入口
│   ├── templates/       # HTML 页面模板 (Login, Index, Profile)
│   └── static/          # 静态资源文件
├── data/
│   └── users.db         # SQLite 数据库文件 (持久化存储)
├── manage.py            # CLI 管理脚本
├── docker-compose.yml   # Docker 编排文件
├── Dockerfile           # 镜像构建文件
└── README.md            # 项目说明文档
```

## Nginx Proxy Manager 集成 (可选)

若要使用本服务保护其他应用，请在 Nginx Proxy Manager 中对应主机的 `Advanced` -> `Custom Nginx Configuration` 或 `Access Lists` 配置中指向本服务的验证接口：

*   **验证地址**: `http://<lab-portal-ip>:8000/verify`
*   **原理**: 当用户访问受保护服务时，NPM 会先请求 `/verify`。如果用户在 Lab Portal 未登录，将返回 401 并在网关层拦截或重定向到登录页。

## 许可证

Internal Use / 私有项目
