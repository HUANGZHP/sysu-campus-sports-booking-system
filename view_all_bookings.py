from db import get_conn
from datetime import datetime, timedelta, date

def view_all_bookings():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 执行多表关联查询，获取详细信息
            sql = """
                SELECT 
                    r.预约ID, 
                    u.姓名 as 预约人, 
                    f.场地名称, 
                    r.预约日期, 
                    t.开始时间, 
                    r.预约类型, 
                    r.状态
                FROM 预约记录 r
                JOIN 用户 u ON r.预约者id = u.用户ID
                JOIN 场地 f ON r.场地ID = f.场地ID
                JOIN 时间段 t ON r.时间段ID = t.时间段ID
                ORDER BY r.预约日期 DESC, t.开始时间 ASC
            """
            cur.execute(sql)
            bookings = cur.fetchall()
            
            if not bookings:
                print("❌ 数据库中暂无预约记录。")
                return

            # 2. 打印表头 (格式化宽度)
            header = f"{'预约ID':<12} | {'预约人':<8} | {'场地名称':<12} | {'日期':<12} | {'时间':<8} | {'类型':<6} | {'状态':<8}"
            print("\n" + "="*95)
            print(header)
            print("-" * 95)

            # 3. 循环打印每一行数据
            for b in bookings:
                # 转换日期和时间对象为字符串
                d_str = b['预约日期'].strftime('%Y-%m-%d') if isinstance(b['预约日期'], (date, datetime)) else str(b['预约日期'])
                
                # 处理 MySQL 的 TIME 类型 (timedelta)
                if isinstance(b['开始时间'], timedelta):
                    t_str = (datetime.min + b['开始时间']).time().strftime('%H:%M')
                else:
                    t_str = str(b['开始时间'])

                line = f"{str(b['预约ID']):<12} | {str(b['预约人']):<8} | {str(b['场地名称']):<12} | {d_str:<12} | {t_str:<8} | {str(b['预约类型']):<6} | {str(b['状态']):<8}"
                print(line)
            
            print("-" * 95)
            print(f"✅ 查询完毕，共计 {len(bookings)} 条预约记录。")
            print("="*95 + "\n")

    except Exception as e:
        print(f"❌ 查询出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_all_bookings()