from db import get_conn
import pymysql

def view_fields():
    conn = get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 直接查询场地表，并关联馆名显示位置
            sql = """
            SELECT 
                f.场地ID, 
                f.场地名称, 
                v.校区,
                f.设施类型, 
                f.可容纳人数, 
                f.预约价格
            FROM 场地 f
            JOIN 场馆 v ON f.场馆ID = v.场馆ID
            ORDER BY f.场地ID ASC
            """
            cur.execute(sql)
            rows = cur.fetchall()

            if not rows:
                print("\n⚠️ 找不到场地！请确保已运行 rebuild_venues_final.py")
                return

            print("\n" + "="*70)
            print(f"{'场地ID':<8} | {'场地名称':<20} | {'类型':<8} | {'容量':<4} | {'价格'}")
            print("-" * 70)

            for r in rows:
                # 格式化输出每一行场地信息
                print(f"{r['场地ID']:<10} | {r['场地名称']:<22} | {r['设施类型']:<10} | {r['可容纳人数']:<6} | {r['预约价格']}")
            
            print("="*70)
            print(f"✅ 查询完毕：当前系统共有 {len(rows)} 个细分场地。")

    except Exception as e:
        print(f"❌ 执行查询时出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_fields()