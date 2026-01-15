from db import get_conn

def clean_for_rebuild():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            print("正在强制清空所有业务记录...")
            
            # 1. 暂时关闭外键约束检查
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # 2. 清空所有业务表（不分先后顺序）
            tables = [
                "预约成员", "预约记录", "钱包流水", 
                "报修单", "信用记录", "帖子点赞", 
                "评论", "帖子", "封场事件", "器材借用"
            ]
            
            for table in tables:
                try:
                    cur.execute(f"TRUNCATE TABLE {table}")
                    print(f"   ✅ 已清空表: {table}")
                except Exception as e:
                    # 如果某些表不存在，直接跳过
                    cur.execute(f"DELETE FROM {table}")
                    print(f"   ✅ 已清理记录: {table}")

            # 3. 重新开启外键约束检查
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            conn.commit()
            print("\n🚀 所有业务数据已彻底清空！外键锁定已解除。")
            print("现在你可以运行 rebuild_venues.py 来重构 1-9 号场馆了。")
    except Exception as e:
        conn.rollback()
        print(f"❌ 清空失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    clean_for_rebuild()