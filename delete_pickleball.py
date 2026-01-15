import pymysql
from db import get_conn

def delete_pickleball():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            print("--- 开始彻底清理匹克球数据 ---")
            
            # 1. 尝试按名称关键字删除场地
            rows1 = cur.execute("DELETE FROM 场地 WHERE 场地名称 LIKE '%匹克球%' OR 设施类型='匹克球'")
            print(f"1. 已清理相关场地记录: {rows1} 条")
            
            # 2. 尝试按名称关键字删除场馆
            rows2 = cur.execute("DELETE FROM 场馆 WHERE 场馆名称 LIKE '%匹克球%'")
            print(f"2. 已清理相关场馆记录: {rows2} 条")
            
            # 3. 额外清理由于之前的错别字可能残留的记录
            rows3 = cur.execute("DELETE FROM 场地 WHERE 设施类型='皮克球' OR 场地名称 LIKE '%皮克球%'")
            rows4 = cur.execute("DELETE FROM 场馆 WHERE 场馆名称 LIKE '%皮克球%'")
            print(f"3. 已清理错别字残留记录: {rows3 + rows4} 条")

            conn.commit()
            print("\n✅ 匹克球场数据已彻底从数据库中抹除。")
            
    except Exception as e:
        conn.rollback()
        print(f"❌ 运行中出现异常: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    delete_pickleball()