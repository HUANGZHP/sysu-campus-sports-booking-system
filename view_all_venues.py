from db import get_conn

def view_all_venues():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 执行 SQL 查询全部场馆 [cite: 4, 52, 88]
            sql = "SELECT 场馆ID, 场馆名称, 校区, 场馆状态 FROM 场馆 ORDER BY 场馆ID ASC"
            cur.execute(sql)
            venues = cur.fetchall()
            
            if not venues:
                print("❌ 数据库中暂无场馆数据。")
                return

            # 2. 打印表头 (格式化宽度)
            header = f"{'场馆ID':<12} | {'场馆名称':<15} | {'校区':<10} | {'状态':<8}"
            print("\n" + "="*55)
            print(header)
            print("-" * 55)

            # 3. 循环打印每一行数据 [cite: 52, 88]
            for v in venues:
                line = f"{str(v['场馆ID']):<12} | {str(v['场馆名称']):<15} | {str(v['校区']):<10} | {str(v['场馆状态']):<8}"
                print(line)
            
            print("-" * 55)
            print(f"✅ 查询完毕，共计 {len(venues)} 个场馆。")
            print("="*55 + "\n")

    except Exception as e:
        print(f"❌ 查询出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_all_venues()