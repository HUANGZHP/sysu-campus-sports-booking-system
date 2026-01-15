import random
from datetime import datetime, timedelta
from db import get_conn
import pymysql

def generate_posts(count=30):
    conn = get_conn()
    now_time = datetime.now()
    
    # 定义一些贴心的社区内容模板
    post_templates = [
        {"title": "[组队] 下午三点西园网球中心有人一起吗？", "content": "水平一般，主要是想出出汗，目前有两人，再来两位！"},
        {"title": "东园健身中心器材太全了！", "content": "今天第一次去，发现卧推架和哑铃都很新，环境也不错，推荐大家去。"},
        {"title": "[寻物] 在乒乓球馆丢了一个白色水杯", "content": "大概是今天中午十二点左右落下的，如果有同学看到请联系我，万分感谢！"},
        {"title": "游泳馆的水温刚刚好", "content": "刚游完回来，水质很清澈，人也不是很多，体验极佳。"},
        {"title": "[吐槽] 刚刚排球馆的灯光好像有个坏了", "content": "希望管理员能去修一下，底角位置有点暗。"},
        {"title": "新手求带：台球馆怎么预约？", "content": "想去打台球，但是不知道是按人头算还是按小时算？"},
        {"title": "[组队] 篮球场3缺1，有大神来带带吗？", "content": "我们在西园篮球场，来个个子高一点的哥们，打半场。"},
        {"title": "羽毛球馆周六上午真的难抢", "content": "大家都是定闹钟抢的吗？每次进去都没位了..."},
    ]

    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            # 1. 获取现有学生 ID
            cur.execute("SELECT 用户ID FROM 用户 WHERE 用户类型='学生'")
            students = cur.fetchall()
            
            if not students:
                print("❌ 错误：数据库中没有学生账号，请先运行 batch_generate_data.py")
                return

            print(f"🚀 开始生成 {count} 条社区帖子...")
            
            posts_data = []
            for i in range(count):
                # 生成唯一帖子ID (基于毫秒级时间戳)
                post_id = int(datetime.now().strftime("%y%m%d%H%M%S")) + i
                
                # 随机选择学生和模板
                u_id = random.choice(students)['用户ID']
                template = random.choice(post_templates)
                
                # 随机化发帖时间（过去 3 天内）
                post_time = now_time - timedelta(
                    days=random.randint(0, 3), 
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                posts_data.append((
                    post_id, u_id, template['title'], template['content'], post_time
                ))

            # 2. 批量插入
            cur.executemany("""
                INSERT INTO 帖子 (帖子id, 用户id, 标题, 内容, 发帖时间) 
                VALUES (%s, %s, %s, %s, %s)
            """, posts_data)

        conn.commit()
        print(f"🎉 成功！已生成 {count} 条社区动态。")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ 生成失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    generate_posts(20) # 默认生成20条
    