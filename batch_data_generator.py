import random
from datetime import datetime, timedelta
from db import get_conn
import pymysql

def generate_only_bookings(count=5000):
    conn = get_conn()
    now_time = datetime.now()
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 1. 动态获取现有的学生 ID
            print("🔍 正在检索现有学生账号...")
            cur.execute("SELECT 用户ID, 组织id FROM 用户 WHERE 用户类型='学生'")
            students = cur.fetchall()
            
            if not students:
                print("❌ 错误：数据库中没有学生账号，请先手动注册一个或运行之前的学生生成脚本。")
                return

            # 2. 动态获取当前的场地和时段
            print("🔍 正在检索场地配置...")
            cur.execute("SELECT 场地ID FROM 场地 WHERE 状态='开放'")
            field_ids = [f['场地ID'] for f in cur.fetchall()]
            
            cur.execute("SELECT 时间段ID FROM 时间段")
            slot_ids = [s['时间段ID'] for s in cur.fetchall()]

            print(f"🚀 开始为 {len(students)} 名学生生成 {count} 条预约记录...")
            
            bookings_data = []
            for j in range(count):
                # 生成唯一预约ID (基于时间戳和序号)
                booking_id = int(datetime.now().strftime("%y%m%d%H%S")) + j
                
                # 从现有学生中随机选一个
                student = random.choice(students)
                u_id = student['用户ID']
                o_id = student['组织id']
                
                # 随机分配场地、时段和未来日期
                f_id = random.choice(field_ids)
                s_id = random.choice(slot_ids)
                booking_date = (now_time + timedelta(days=random.randint(1, 7))).date()
                
                bookings_data.append((
                    booking_id, f_id, booking_date, s_id, u_id, o_id, 
                    random.choice(['个人', '组队']), '已预约', now_time
                ))

            # 3. 批量插入预约记录
            cur.executemany("""
                INSERT INTO 预约记录 (预约ID, 场地ID, 预约日期, 时间段ID, 预约者id, 组织id, 预约类型, 状态, 创建时间) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, bookings_data)

        conn.commit()
        print(f"🎉 任务成功！已成功插入 {count} 条预约记录，均匀分布在 {len(field_ids)} 个场地中。")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 运行失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    generate_only_bookings(5000)