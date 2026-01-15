from db import get_conn
from datetime import datetime

def view_all_users():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 执行 SQL 查询全部学生 [cite: 7, 127]
            # 我们排除掉管理员，只看学生
            sql = "SELECT 用户ID, 学号或工号, 姓名, 用户类型, 信用分, 账号状态 FROM 用户 WHERE 用户类型='学生' ORDER BY 用户ID ASC"
            cur.execute(sql)
            users = cur.fetchall()
            
            if not users:
                print("❌ 数据库中暂无学生数据。")
                return

            # 2. 打印表头
            header = f"{'用户ID':<15} | {'学号':<15} | {'姓名':<10} | {'信用分':<8} | {'状态':<8}"
            print("\n" + "="*70)
            print(header)
            print("-" * 70)

            # 3. 循环打印每一行数据 [cite: 127]
            for u in users:
                line = f"{str(u['用户ID']):<15} | {str(u['学号或工号']):<15} | {str(u['姓名']):<10} | {str(u['信用分']):<8} | {str(u['账号状态']):<8}"
                print(line)
            
            print("-" * 70)
            print(f"✅ 查询完毕，共计 {len(users)} 名学生。")
            print("="*70 + "\n")

    except Exception as e:
        print(f"❌ 查询出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    view_all_users()