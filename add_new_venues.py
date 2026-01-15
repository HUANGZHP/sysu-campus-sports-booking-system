import pymysql
from db import get_conn
from datetime import datetime
import time
import random

def add_venues_and_fields():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 彻底清理之前测试产生的旧数据，确保环境干净
            print("正在清理旧数据...")
            types_to_clean = ['游泳', '网球', '击剑', '健身', '匹克球', '皮克球']
            cur.execute("DELETE FROM 场地 WHERE 设施类型 IN %s", (types_to_clean,))
            cur.execute("DELETE FROM 场馆 WHERE 场馆名称 IN ('游泳馆', '网球中心', '击剑馆', '健身中心', '匹克球场', '皮克球场')")

            # 2. 定义场馆配置
            # 格式：场馆名称, 校区, 运动类型, 场地数量, 单价, 可容纳人数
            new_data = [
                ("游泳馆", "东园", "游泳", 1, 20, 50),   # 游泳馆只要一个场地，限容50人
                ("健身中心", "东园", "健身", 1, 15, 30), # 健身房只要一个场地
                ("网球中心", "西园", "网球", 4, 40, 4), 
                ("击剑馆", "北园", "击剑", 6, 60, 2),   
                ("匹克球场", "西园", "匹克球", 4, 30, 4) 
            ]

            for v_name, campus, f_type, count, price, cap in new_data:
                # 生成场馆ID
                vid = int(datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(100, 999)))
                
                cur.execute("""
                    INSERT INTO 场馆 (场馆ID, 场馆名称, 校区, 场馆状态, 图片) 
                    VALUES (%s, %s, %s, '开放', 'default.jpg')
                """, (vid, v_name, campus))
                
                # 3. 按照 [校区][场馆名称][序号] 规范命名
                for i in range(1, count + 1):
                    fid = int(f"{vid}{i:02d}") 
                    
                    # 统一命名逻辑：[校区][场馆名称][序号][号场]
                    if count == 1:
                        # 只有一个场地的（如游泳馆、健身房）
                        f_display_name = f"{campus}{v_name}"
                    else:
                        # 有多个场地的（如网球、击剑、匹克球）
                        f_display_name = f"{campus}{v_name}{i}号场"
                    
                    cur.execute("""
                        INSERT INTO 场地 (场地ID, 场馆ID, 场地名称, 设施类型, 可容纳人数, 状态, 预约价格) 
                        VALUES (%s, %s, %s, %s, %s, '开放', %s)
                    """, (fid, vid, f_display_name, f_type, cap, price))
                
                print(f"✅ 已添加：{campus}{v_name} (包含 {count} 个场地)")
                time.sleep(0.1) 

            conn.commit()
            print("\n🚀 场馆数据已按照要求重新录入！")
    except Exception as e:
        conn.rollback()
        print(f"❌ 运行失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_venues_and_fields()