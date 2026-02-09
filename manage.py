import os
import sys
import sqlite3
import subprocess
import time
import argparse
from datetime import datetime

# 尝试导入 passlib，如果不存在则提示安装
try:
    from passlib.context import CryptContext
except ImportError:
    print("\n错误: 未找到 'passlib' 模块。")
    print("请在主机上安装依赖: pip install passlib bcrypt")
    print("或者确保运行环境已安装该库。\n")
    sys.exit(1)

# 配置密码加密 (与 main.py 保持一致)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 数据库路径 (相对于 manage.py)
DB_PATH = os.path.join("data", "users.db")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 60)
    print("           Lab Portal 综合管理控制台")
    print("=" * 60)

def connect_db():
    if not os.path.exists(DB_PATH):
        print(f"错误: 数据库文件不存在: {DB_PATH}")
        print("请先启动服务生成数据文件。")
        return None
    return sqlite3.connect(DB_PATH)

# ================= 用户管理功能 =================

def list_users():
    conn = connect_db()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, account, username, role FROM users")
        users = cursor.fetchall()
        print("\n[ 用户列表 ]")
        print(f"{'ID':<5} | {'账号':<15} | {'用户名':<15} | {'权限组':<10}")
        print("-" * 60)
        for u in users:
            print(f"{u[0]:<5} | {u[1]:<15} | {u[2]:<15} | {u[3]:<10}")
    except Exception as e:
        print(f"读取用户失败: {e}")
    finally:
        conn.close()

def add_user():
    account = input("请输入新账号 (Account, 留空取消): ").strip()
    if not account: return
    
    username = input(f"请输入用户名 (Username, 默认同账号): ").strip()
    if not username: username = account
    
    password = input("请输入密码: ").strip()
    if not password: return
    
    password_hash = pwd_context.hash(password)
    
    conn = connect_db()
    if not conn: return
    try:
        # 默认为 user 权限
        conn.execute("INSERT INTO users (account, username, password_hash, role) VALUES (?, ?, ?, 'user')", (account, username, password_hash))
        conn.commit()
        print(f"\n成功添加用户: {username} ({account})")
    except sqlite3.IntegrityError:
        print(f"\n错误: 账号或用户名已存在")
    except Exception as e:
        print(f"\n操作失败: {e}")
    finally:
        conn.close()

def delete_user():
    username = input("请输入要删除的用户名 (留空取消): ").strip()
    if not username: return
    
    confirm = input(f"确认删除用户 '{username}'? (y/n): ").lower()
    if confirm != 'y': return
    
    conn = connect_db()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE account=?", (username,)) # 这里变量名还是 username 但实际是 account
        if cursor.rowcount > 0:
            conn.commit()
            print(f"\n已删除用户: {username}")
        else:
            print(f"\n未找到用户: {username}")
    except Exception as e:
        print(f"\n操作失败: {e}")
    finally:
        conn.close()

def change_password():
    username = input("请输入用户名 (留空取消): ").strip()
    if not username: return
    new_password = input("请输入新密码: ").strip()
    if not new_password: return
    
    password_hash = pwd_context.hash(new_password)
    
    conn = connect_db()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash=? WHERE account=?", (password_hash, username)) # username 变量存的是 account
        if cursor.rowcount > 0:
            conn.commit()
            print(f"\n用户 '{username}' 的密码已更新")
        else:
            print(f"\n未找到用户: {username}")
    except Exception as e:
        print(f"\n操作失败: {e}")
    finally:
        conn.close()

def change_role():
    account = input("请输入用户账号 (留空取消): ").strip()
    if not account: return
    
    print("可用权限: user, admin")
    new_role = input("请输入新权限组: ").strip().lower()
    if new_role not in ['user', 'admin']:
        print("无效的权限组")
        return

    conn = connect_db()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role=? WHERE account=?", (new_role, account))
        if cursor.rowcount > 0:
            conn.commit()
            print(f"\n用户 '{account}' 的权限已更新为 {new_role}")
        else:
            print(f"\n未找到用户: {account}")
    except Exception as e:
        print(f"\n操作失败: {e}")
    finally:
        conn.close()

def manage_users_menu():
    while True:
        clear_screen()
        print_header()
        print("\n[ 用户管理 ]")
        print("1. 查看列表")
        print("2. 添加用户")
        print("3. 删除用户")
        print("4. 修改密码")
        print("5. 修改权限")
        print("0. 返回上级")
        
        choice = input("\n选项: ").strip()
        
        if choice == '0': break
        elif choice == '1':
            list_users()
            input("\n按回车键继续...")
        elif choice == '2':
            add_user()
            input("\n按回车键继续...")
        elif choice == '3':
            delete_user()
            input("\n按回车键继续...")
        elif choice == '4':
            change_password()
            input("\n按回车键继续...")
        elif choice == '5':
            change_role()
            input("\n按回车键继续...")

# ================= 日志查看功能 =================

def view_audit_logs():
    print("\n--- 日志筛选 (直接回车跳过) ---")
    user_filter = input("用户名包含: ").strip()
    action_filter = input("行为类型包含 (e.g. LOGIN): ").strip()
    limit_str = input("显示条数 (默认50, 0为全部): ").strip()
    
    limit = 50
    if limit_str.isdigit():
        limit = int(limit_str)
    
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    
    if user_filter:
        query += " AND username LIKE ?"
        params.append(f"%{user_filter}%")
    if action_filter:
        query += " AND action LIKE ?"
        params.append(f"%{action_filter}%")
    
    query += " ORDER BY timestamp DESC"
    
    if limit > 0:
        query += f" LIMIT {limit}"
    
    conn = connect_db()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        print("\n[ 审计日志 ]")
        # ID | User | Action | IP | Time
        print(f"{'ID':<4} | {'用户':<12} | {'行为':<15} | {'IP地址':<15} | {'时间'}")
        print("-" * 80)
        for row in rows:
            # row: id, username, action, ip_address, timestamp
            print(f"{row[0]:<4} | {row[1]:<12} | {row[2]:<15} | {row[3]:<15} | {row[4]}")
            
        print(f"\n共显示 {len(rows)} 条记录")
        
    except Exception as e:
        print(f"查询日志失败: {e}")
    finally:
        conn.close()

def view_logs_menu():
    while True:
        clear_screen()
        print_header()
        print("\n[ 日志中心 ]")
        print("1. 查询审计日志 (Audit Logs)")
        print("2. 实时系统日志 (Docker Logs)")
        print("0. 返回上级")
        
        choice = input("\n选项: ").strip()
        
        if choice == '0': break
        elif choice == '1':
            view_audit_logs()
            input("\n按回车键继续...")
        elif choice == '2':
            print("\n正在打开 Docker 实时日志 (按 Ctrl+C 退出)...")
            try:
                subprocess.run(["docker", "compose", "logs", "-f", "--tail=50", "lab-portal"])
            except KeyboardInterrupt:
                pass
            except Exception as e:
                print(f"无法运行 Docker 命令: {e}")
                input()

# ================= 系统维护功能 =================

def run_docker(cmd):
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"命令执行出错: {e}")
    except Exception as e:
        print(f"执行失败: {e}")

def system_menu():
    while True:
        clear_screen()
        print_header()
        print("\n[ 系统维护 ]")
        print("1. 服务状态 (Status)")
        print("2. 重启服务 (Restart)")
        print("3. 关闭服务 (Stop)")
        print("4. 启动服务 (Start)")
        print("0. 返回上级")
        
        choice = input("\n选项: ").strip()
        
        if choice == '0': break
        elif choice == '1':
            run_docker(["docker", "compose", "ps"])
            input("\n按回车键继续...")
        elif choice == '2':
            print("正在重启...")
            run_docker(["docker", "compose", "restart"])
            print("完成。")
            input("\n按回车键继续...")
        elif choice == '3':
            print("正在停止...")
            run_docker(["docker", "compose", "stop"])
            input("\n按回车键继续...")
        elif choice == '4':
            print("正在启动...")
            run_docker(["docker", "compose", "start"])
            input("\n按回车键继续...")

# ================= 主程序 =================

def main():
    while True:
        clear_screen()
        print_header()
        print("\n[ 主菜单 ]")
        print("1. 用户管理")
        print("2. 日志中心")
        print("3. 系统维护")
        print("0. 退出")
        
        choice = input("\n请选择: ").strip()
        
        if choice == '0':
            print("再见!")
            sys.exit(0)
        elif choice == '1': manage_users_menu()
        elif choice == '2': view_logs_menu()
        elif choice == '3': system_menu()
        else:
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已强制退出")
        sys.exit(0)
