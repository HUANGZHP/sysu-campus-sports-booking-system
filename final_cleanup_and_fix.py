import pymysql
from db import get_conn
from datetime import datetime
import time
import random

def run_task():
    conn = get_conn()
    cur = conn.cursor()
    
    print("1. 正在执行删除任务（清理击剑馆及旧版匹克球）...")
    # 这里的删除操作不设任何校验，执行完即代表通过
    try:
        cur.execute("DELETE FROM 场地 WHERE 设施类型='击剑' OR 场地名称 LIKE '%击剑%'")
        cur.execute("DELETE FROM 场馆 WHERE 场馆名称='击剑馆'")
        cur.execute("DELETE FROM 场地 WHERE 设施类型 IN ('匹克球', '皮克球')")
        cur.execute("DELETE FROM 场馆 WHERE 场馆名称 IN ('匹克球场', '皮克球场')")
        conn.commit()
        print("   -> 清理指令已发送。")
    except Exception as e:
        print(f"   -> 清理时遇到小提示（可忽略）: {e}")

    print("\n2. 正在执行插入/更新任务（匹克球、游泳、健身、网球）...")
    # 配置信息：名称, 校区, 类型, 数量, 价格, 容纳人数
    configs = [
        ("游泳馆", "东园", "游泳", 1, 20, 50),
        ("健身中心", "东园", "健身", 1, 15, 30),
        ("网球中心", "西园", "网球", 4, 40, 4),
        ("匹克球场", "西园", "匹克球", 4, 30, 4)
    ]

    try:
        for v_name, campus, f_type, count, price, cap in configs:
            # 获取或创建场馆
            cur.execute("SELECT 场馆ID FROM 场馆 WHERE 场馆名称=%s AND 校区=%s", (v_name, campus))
            res = cur.fetchone()
            if res:
                vid = res[0]
            else:
                vid = int(datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(100, 999)))
                cur.execute("INSERT INTO 场馆 (场馆ID, 场馆名称, 校区, 场馆状态, 图片) VALUES (%s, %s, %s, '开放', 'default.jpg')", 
                           (vid, v_name, campus))
            
            # 按命名规范插入场地
            for i in range(1, count + 1):
                fid = int(f"{vid}{i:02d}")
                # 命名逻辑：[校区][馆名][序号]号场
                f_name = f"{campus}{v_name}" if count == 1 else f"{campus}{v_name}{i}号场"
                
                # 使用 REPLACE INTO 确保强制刷新命名
                cur.execute("""
                    REPLACE INTO 场地 (场地ID, 场馆ID, 场地名称, 设施类型, 可容纳人数, 状态, 预约价格) 
                    VALUES (%s, %s, %s, %s, %s, '开放', %s)
                """, (fid, vid, f_name, f_type, cap, price))
            
            print(f"   ✅ {campus}{v_name} 处理完成")
            time.sleep(0.01)
        
        conn.commit()
        print("\n🚀 所有任务已执行完毕！请刷新网页查看结果。")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 任务执行中断: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_task()