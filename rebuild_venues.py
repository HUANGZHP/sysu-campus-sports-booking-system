from db import get_conn

def rebuild_venues():
    conn = get_conn()
    cur = conn.cursor()
    try:
        print("1. 正在强制清空旧的场馆与场地定义...")
        # 强制关闭外键检查并清表
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        cur.execute("TRUNCATE TABLE 场地")
        cur.execute("TRUNCATE TABLE 场馆")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()

        # 定义 1-9 号场馆
        venues = [
            (1, "篮球馆", "东园"), (2, "篮球馆", "西园"),
            (3, "羽毛球馆", "东园"), (4, "排球馆", "西园"),
            (5, "乒乓球馆", "东园"), (6, "台球馆", "西园"),
            (7, "游泳馆", "东园"), (8, "网球中心", "西园"),
            (9, "健身中心", "东园")
        ]

        # 场地配置：馆ID, 运动类型, 数量, 价格, 容纳人数
        fields_config = [
            (1, "篮球", 2, 10, 10), (2, "篮球", 1, 20, 10),
            (3, "羽毛球", 1, 15, 6), (4, "排球", 1, 18, 12),
            (5, "乒乓球", 1, 15, 4), (6, "台球", 1, 25, 4),
            (7, "游泳", 1, 20, 50), (8, "网球", 4, 40, 4),
            (9, "健身", 1, 15, 30)
        ]

        print("2. 正在按 1-9 顺序重新插入场馆...")
        for vid, name, campus in venues:
            cur.execute("""
                INSERT INTO 场馆 (场馆ID, 场馆名称, 校区, 场馆状态, 图片) 
                VALUES (%s, %s, %s, '开放', 'default.jpg')
            """, (vid, name, campus))

        print("3. 正在生成规范命名的场地 (ID: 11, 12...)...")
        for vid, f_type, count, price, cap in fields_config:
            # 这里的 i 循环保证了命名和 ID 的唯一性
            for i in range(1, count + 1):
                fid = vid * 10 + i 
                suffix = str(i) if count > 1 else ""
                
                # 获取校区信息用于命名
                campus = "东园" if vid in [1, 3, 5, 7, 9] else "西园"
                # 获取馆名
                v_name = "篮球场" if f_type == "篮球" else ("网球中心" if f_type == "网球" else f_type + "馆")
                if f_type == "健身": v_name = "健身中心"

                f_display_name = f"{campus}{v_name}{suffix}"
                
                cur.execute("""
                    INSERT INTO 场地 (场地ID, 场馆ID, 场地名称, 设施类型, 可容纳人数, 状态, 预约价格) 
                    VALUES (%s, %s, %s, %s, %s, '开放', %s)
                """, (fid, vid, f_display_name, f_type, cap, price))

        conn.commit()
        print("\n🚀 重构任务执行完毕！")
        print("请直接刷新网页，你会看到 ID 为 1-9 的整洁场馆列表。")

    except Exception as e:
        conn.rollback()
        print(f"❌ 运行报错: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    rebuild_venues()