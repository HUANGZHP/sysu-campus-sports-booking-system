import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    # 注意：这里我们去掉了 autocommit=True，改为默认不自动提交
    # 这样我们在 app.py 里就可以使用 conn.begin(), conn.commit(), conn.rollback() 了
    return pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "大学体育馆预约系统"),
        charset="utf8mb4",
        cursorclass=DictCursor
    )