import random
from datetime import datetime, timedelta
from db import get_conn
import pymysql

def fill_details():
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 1. 检查基础数据是否存在
            cur.execute("SELECT 用户ID FROM 用户 WHERE 用户类型='学生'")
            u_ids = [r['用户ID'] for r in cur.fetchall()]
            
            cur.execute("SELECT 帖子id FROM 帖子")
            p_ids = [r['帖子id'] for r in cur.fetchall()]
            
            cur.execute("SELECT 预约ID FROM 预约记录")
            b_ids = [r['预约ID'] for r in cur.fetchall()]

            if not u_ids:
                print("⚠️ 数据库中没有学生，请先注册或导入学生数据。")
                return

            print(f"🚀 正在为 {len(u_ids)} 名学生生成业务细节...")

            # 2. 生成评论 (如果有帖子)
            if p_ids:
                print("💬 正在生成互动评论与点赞...")
                comments = ["赞一个！", "非常有参考价值。", "感谢分享！", "这就是我想找的。", "已收藏。"]
                for p_id in p_ids:
                    # 每个帖子随机 1-3 条评论
                    for _ in range(random.randint(1, 3)):
                        cur.execute("INSERT INTO 评论 (用户id, 帖子id, 内容, 评论时间) VALUES (%s, %s, %s, %s)",
                                    (random.choice(u_ids), p_id, random.choice(comments), datetime.now()))
                        # 随机点赞
                        try:
                            cur.execute("INSERT INTO 帖子点赞 (用户id, 帖子id, 点赞时间) VALUES (%s, %s, %s)",
                                        (random.choice(u_ids), p_id, datetime.now()))
                        except: pass # 忽略重复点赞报错

            # 3. 生成钱包流水 (为每个学生生成 2-5 笔充值/消费)
            print("💰 正在生成钱包流水记录...")
            for u_id in u_ids:
                for _ in range(random.randint(2, 5)):
                    amount = random.choice([10, 20, 50, -15, -40])
                    cur.execute("""INSERT INTO 钱包流水 (用户id, 变动金额, 变动原因, 变动时间) 
                                   VALUES (%s, %s, %s, %s)""",
                                (u_id, amount, "场地预约" if amount < 0 else "在线充值", datetime.now()))

            # 4. 生成信用记录
            print("⭐ 正在生成信用分变动记录...")
            for u_id in u_ids:
                cur.execute("INSERT INTO 信用记录 (用户ID, 变动分值, 变动原因, 变动时间) VALUES (%s, %s, %s, %s)",
                            (u_id, 2, "按时到达场馆", datetime.now()))

            # 5. 生成器材借用 (模拟一些借球拍记录)
            print("🏸 正在生成器材借用记录...")
            equipments = ["羽毛球拍", "乒乓球拍", "篮球", "网球拍"]
            for u_id in u_ids:
                cur.execute("""INSERT INTO 器材借用 (用户id, 器材名称, 状态, 借用时间) 
                               VALUES (%s, %s, '已归还', %s)""",
                            (u_id, random.choice(equipments), datetime.now() - timedelta(days=1)))

            conn.commit()
            print("\n✅ 业务细节填充完毕！现在各模块的数据都非常完整了。")

    except Exception as e:
        conn.rollback()
        print(f"❌ 运行出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fill_details()