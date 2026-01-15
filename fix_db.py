from db import get_conn
import pymysql

print("🚀 正在连接数据库...")
conn = get_conn()

try:
    with conn.cursor() as cur:
        print("🛠️ 正在检测 '器材' 表结构...")
        
        # 尝试直接添加 '图片' 列
        # DEFAULT 'default_equipment.jpg' 意思是如果没传图片，默认用这张图
        sql = "ALTER TABLE 器材 ADD COLUMN 图片 VARCHAR(255) DEFAULT 'default_equipment.jpg'"
        
        print(f"正在执行: {sql}")
        cur.execute(sql)
        conn.commit()
        
        print("✅ 成功！'图片' 字段已添加到数据库！")

except pymysql.err.OperationalError as e:
    # 错误代码 1060 代表字段已存在
    if e.args[0] == 1060:
        print("✅ '图片' 字段已经存在了，无需重复添加。")
    else:
        print(f"❌ 数据库操作失败: {e}")
except Exception as e:
    print(f"❌ 发生未知错误: {e}")
finally:
    conn.close()
    print("------------------------------------------------")
    print("🎉 修复完成！现在请重新运行 python app.py")