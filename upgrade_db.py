from db import get_conn
import pymysql

def upgrade():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            print("🚀 正在升级数据库...")
            # [cite_start]创建点赞记录表 [cite: 44, 45]
            cur.execute("""
                CREATE TABLE IF NOT EXISTS 帖子点赞 (
                    点赞ID BIGINT PRIMARY KEY,
                    帖子ID BIGINT NOT NULL,
                    用户ID BIGINT NOT NULL,
                    创建时间 DATETIME NOT NULL,
                    UNIQUE KEY uk_post_user (帖子ID, 用户ID),
                    CONSTRAINT fk_like_post FOREIGN KEY (帖子ID) REFERENCES 帖子(帖子id) ON DELETE CASCADE,
                    CONSTRAINT fk_like_user FOREIGN KEY (用户ID) REFERENCES 用户(用户ID)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            conn.commit()
            print("✅ 数据库升级成功！")
    except Exception as e:
        print(f"❌ 升级失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade()