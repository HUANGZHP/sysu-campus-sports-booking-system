import os
from datetime import datetime, date as date_cls, timedelta, time
import calendar
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
from db import get_conn
import pymysql
from pymysql.cursors import DictCursor 

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET", "dev-secret-change-me")

# 配置上传文件夹
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER), exist_ok=True)

# -------------------------
# 辅助工具函数
# -------------------------
def login_required(): return "user_id" in session
def admin_required(): return "user_id" in session and session.get("role") == "管理员"
def current_user():
    if "user_id" not in session: return None
    return {"user_id": session["user_id"], "name": session.get("name"), "role": session.get("role"), "org_id": session.get("org_id")}
def parse_date(s: str) -> date_cls: return datetime.strptime(s, "%Y-%m-%d").date()

# -------------------------
# 基础路由
# -------------------------
@app.get("/")
def home():
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") == "管理员": return redirect(url_for("admin_dashboard"))
    return redirect(url_for("dashboard"))

@app.get("/login")
def login(): return render_template("login.html")

@app.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            sql = "SELECT u.用户ID, u.姓名, u.用户类型, u.组织id FROM 账号 a JOIN 用户 u ON a.用户ID = u.用户ID WHERE a.登录名=%s AND a.登录密码=SHA2(%s, 256) AND a.状态='正常' AND u.账号状态='正常' LIMIT 1"
            cur.execute(sql, (username, password))
            row = cur.fetchone()
    finally: conn.close()
    if not row: flash("账号或密码错误"); return redirect(url_for("login"))
    session["user_id"] = int(row["用户ID"])
    session["name"] = row["姓名"]
    session["role"] = row["用户类型"]
    session["org_id"] = int(row["组织id"])
    if row["用户类型"] == "管理员": return redirect(url_for("admin_dashboard"))
    return redirect(url_for("dashboard"))

@app.get("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

# ================= 管理员模块 =================

@app.get("/admin")
def admin_dashboard():
    if not admin_required(): return redirect(url_for("login"))
    return render_template("admin_index.html", user=current_user())

@app.route("/admin/venues", methods=["GET", "POST"])
def admin_venues():
    if not admin_required(): return redirect(url_for("login"))
    conn = get_conn()
    if request.method == "POST":
        action = request.form.get("action")
        fid = request.form.get("field_id")
        
        # --- 1. 一键保存 (update_all) ---
        if action == "update_all":
            new_v_name = request.form.get("new_venue_name")
            new_f_name = request.form.get("new_field_name")
            new_price = request.form.get("price")
            new_capacity = request.form.get("capacity")
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    cur.execute("SELECT 场馆ID FROM 场地 WHERE 场地ID=%s", (fid,))
                    res = cur.fetchone()
                    if res:
                        vid = res['场馆ID']
                        cur.execute("UPDATE 场馆 SET 场馆名称=%s WHERE 场馆ID=%s", (new_v_name, vid))
                        cur.execute("""
                            UPDATE 场地 SET 场地名称=%s, 预约价格=%s, 可容纳人数=%s WHERE 场地ID=%s
                        """, (new_f_name, new_price, new_capacity, fid))
                conn.commit()
                flash("✅ 场馆及场地信息已成功更新")
            except Exception as e:
                conn.rollback(); flash(f"❌ 更新失败: {str(e)}")
            finally: conn.close()
            return redirect(url_for("admin_venues"))

        # --- 2. 核心修复：添加场馆/场地 (add) 包含图片处理 ---
        elif action == "add":
            try:
                campus = request.form.get("campus")
                v_name = request.form.get("venue_name")
                f_name = request.form.get("field_name")
                f_type = request.form.get("facility_type")
                cap = request.form.get("capacity") or 10
                price = request.form.get("price") or 0
                
                # ✨ 新增：处理图片上传逻辑
                image_filename = 'default.jpg'
                if "image" in request.files:
                    file = request.files['image']
                    if file and file.filename != '':
                        fname = secure_filename(file.filename)
                        image_filename = f"vn_{int(datetime.now().timestamp())}_{fname}"
                        # 确保路径准确
                        file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], image_filename))

                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    # 检查场馆是否存在
                    cur.execute("SELECT 场馆ID FROM 场馆 WHERE 场馆名称=%s AND 校区=%s", (v_name, campus))
                    row = cur.fetchone()
                    
                    if row:
                        vid = row['场馆ID']
                        # 如果上传了新图，则更新该场馆的封面图
                        if image_filename != 'default.jpg':
                            cur.execute("UPDATE 场馆 SET 图片=%s WHERE 场馆ID=%s", (image_filename, vid))
                    else:
                        vid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                        # 插入新场馆时带上图片
                        cur.execute("INSERT INTO 场馆 (场馆ID, 场馆名称, 校区, 场馆状态, 图片) VALUES (%s, %s, %s, '开放', %s)", 
                                   (vid, v_name, campus, image_filename))
                    
                    # 插入新场地 (修复 %s 参数匹配)
                    fid_new = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]) + 1
                    cur.execute("""
                        INSERT INTO 场地 (场地ID, 场馆ID, 场地名称, 设施类型, 可容纳人数, 状态, 预约价格) 
                        VALUES (%s, %s, %s, %s, %s, '开放', %s)
                    """, (fid_new, vid, f_name, f_type, cap, price))
                conn.commit()
                flash("✅ 场地及其展示图已成功添加")
            except Exception as e:
                conn.rollback(); flash(f"❌ 添加失败: {str(e)}")
            finally: conn.close()
            return redirect(url_for("admin_venues"))

        # --- 3. 核心修复：单独传图逻辑 ---
        elif action == "upload_image":
            if "image" in request.files:
                file = request.files['image']
                if file and file.filename != '':
                    try:
                        fname = secure_filename(file.filename)
                        image_filename = f"field_{int(datetime.now().timestamp())}_{fname}"
                        file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], image_filename))
                        
                        conn.begin()
                        with conn.cursor(DictCursor) as cur:
                            # 更新场馆展示图
                            cur.execute("UPDATE 场馆 v JOIN 场地 f ON v.场馆ID = f.场馆ID SET v.图片 = %s WHERE f.场地ID = %s", 
                                       (image_filename, fid))
                        conn.commit(); flash("✅ 图片已成功更新")
                    except Exception as e:
                        conn.rollback(); flash(f"❌ 传图失败: {e}")
                    finally: conn.close()
            return redirect(url_for("admin_venues"))

        # --- 4. 核心修复：彻底删除场地 (级联删除) ---
        elif action == "delete_field":
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    # ✨ 按照数据库外键依赖顺序级联删除
                    cur.execute("DELETE FROM `封场事件` WHERE `场地ID`=%s", (fid,))
                    cur.execute("DELETE FROM `公告` WHERE `场地ID`=%s", (fid,))
                    cur.execute("DELETE FROM `报修单` WHERE `场地ID`=%s", (fid,))
                    # 级联删除预约记录和其关联的成员
                    cur.execute("DELETE FROM `预约成员` WHERE `预约id` IN (SELECT `预约ID` FROM `预约记录` WHERE `场地ID`=%s)", (fid,))
                    cur.execute("DELETE FROM `预约记录` WHERE `场地ID`=%s", (fid,))
                    # 最后删除场地本体
                    cur.execute("DELETE FROM `场地` WHERE `场地ID`=%s", (fid,))
                conn.commit()
                flash("✅ 场地及所有关联记录已彻底清除")
            except Exception as e:
                conn.rollback(); flash(f"❌ 删除失败: {str(e)}")
            finally: conn.close()
            return redirect(url_for("admin_venues"))
            
        return redirect(url_for("admin_venues"))

    # GET 请求逻辑保持不变
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT f.*, v.场馆名称, v.校区, v.图片 FROM 场地 f JOIN 场馆 v ON f.场馆ID=v.场馆ID ORDER BY v.校区, v.场馆名称")
            rows = cur.fetchall()
    finally: conn.close()
    return render_template("admin_venues.html", user=current_user(), rows=rows)

# [管理员] 报修管理
@app.route("/admin/repairs", methods=["GET", "POST"])
def admin_repairs():
    if not admin_required(): return redirect(url_for("login"))
    conn = get_conn()
    if request.method == "POST":
        try:
            conn.begin()
            with conn.cursor(DictCursor) as cur: cur.execute("UPDATE 报修单 SET 状态='已修复' WHERE 报修ID=%s", (request.form.get("repair_id"),))
            conn.commit(); flash("状态更新")
        except: conn.rollback()
        finally: conn.close()
        return redirect(url_for("admin_repairs"))
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT r.*, f.场地名称, v.场馆名称, u.姓名 as 报修人 FROM 报修单 r JOIN 场地 f ON r.场地ID=f.场地ID JOIN 场馆 v ON f.场馆ID=v.场馆ID JOIN 用户 u ON r.报修人ID=u.用户ID ORDER BY r.状态 DESC")
            rows = cur.fetchall()
    finally: conn.close()
    return render_template("admin_repairs.html", user=current_user(), rows=rows)

@app.get("/admin/bookings")
def admin_bookings():
    if not admin_required(): return redirect(url_for("login"))
    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT r.*, u.姓名, u.学号或工号, f.场地名称, v.场馆名称, t.开始时间, t.结束时间 FROM 预约记录 r JOIN 用户 u ON r.预约者id=u.用户ID JOIN 场地 f ON r.场地ID=f.场地ID JOIN 场馆 v ON f.场馆ID=v.场馆ID JOIN 时间段 t ON r.时间段ID=t.时间段ID ORDER BY r.预约日期 DESC LIMIT 100")
            rows = cur.fetchall()
            for r in rows:
                if isinstance(r['开始时间'], timedelta): r['开始时间'] = (datetime.min + r['开始时间']).time()
                if isinstance(r['结束时间'], timedelta): r['结束时间'] = (datetime.min + r['结束时间']).time()
    finally: conn.close()
    return render_template("admin_bookings.html", user=current_user(), rows=rows)

# [器材管理] 支持图片 + 级联删除
@app.route("/admin/equipment", methods=["GET", "POST"])
def admin_equipment():
    if not admin_required(): return redirect(url_for("login"))
    conn = get_conn()
    if request.method == "POST":
        action = request.form.get("action")
        
        # 1. 删除逻辑 (级联删除) - 原有逻辑保持不变
        if action == "delete":
            eq_id = request.form.get("eq_id")
            if not eq_id:
                flash("错误：未获取到器材ID")
                return redirect(url_for("admin_equipment"))
            
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    # 先删除历史借用记录
                    cur.execute("DELETE FROM 器材借用 WHERE 器材id=%s", (eq_id,))
                    # 再删除器材
                    cur.execute("DELETE FROM 器材 WHERE 器材id=%s", (eq_id,))
                conn.commit()
                flash("✅ 删除成功")
            except Exception as e:
                conn.rollback()
                flash(f"删除失败: {e}")
            finally:
                conn.close()
            return redirect(url_for("admin_equipment"))

        # --- 新增功能：修改逻辑 (Update) ---
        elif action == "update":
            eid, new_total, new_cost = request.form.get("eq_id"), int(request.form.get("total")), int(request.form.get("cost"))
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    # 1. 查出当前的库存状态
                    cur.execute("SELECT 总数量, 可用数量 FROM 器材 WHERE 器材id=%s", (eid,))
                    old = cur.fetchone()
                    
                    # 2. 计算当前已经借出的数量 (总数 - 可用数)
                    borrowed_count = old['总数量'] - old['可用数量']
                    
                    # 3. 校验：新总数不能低于已借出的数量
                    if new_total < borrowed_count:
                        raise Exception(f"❌ 更新失败：当前已有 {borrowed_count} 个器材在借，总库存不能低于此数。")
                    
                    # 4. 计算新的可用数量 = 新总数 - 已借出数
                    new_available = new_total - borrowed_count

                    cur.execute("UPDATE 器材 SET 费用=%s, 总数量=%s, 可用数量=%s WHERE 器材id=%s", 
                            (new_cost, new_total, new_available, eid))
                conn.commit(); flash("✅ 器材库存及价格已成功更新")
            except Exception as e:
                conn.rollback(); flash(str(e))
            finally: conn.close()
            return redirect(url_for("admin_equipment"))
        # -----------------------------------

        # 2. 添加逻辑 - 原有逻辑保持不变
        try:
            conn.begin()
            with conn.cursor(DictCursor) as cur:
                name = request.form.get("name")
                total = int(request.form.get("total"))
                cost = int(request.form.get("cost"))
                
                cur.execute("SELECT 器材ID FROM 器材 WHERE 名称=%s", (name,))
                existing = cur.fetchone()
                
                image_filename = 'default_equipment.jpg'
                if "image" in request.files:
                    f = request.files['image']
                    if f and f.filename:
                        try:
                            fname = secure_filename(f.filename)
                            new_name = f"eq_{int(datetime.now().timestamp())}_{fname}"
                            f.save(os.path.join(app.config['UPLOAD_FOLDER'], new_name))
                            image_filename = new_name
                        except: pass

                if existing:
                    flash("器材名称已存在")
                else:
                    cur.execute("SELECT 场馆ID FROM 场馆 LIMIT 1")
                    vid_row = cur.fetchone()
                    vid = vid_row['场馆ID'] if vid_row else 0
                    eid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                    # 请确保数据库 '器材' 表有 '图片' 字段
                    cur.execute("INSERT INTO 器材 (器材ID, 场馆ID, 名称, 总数量, 可用数量, 费用, 图片) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                                (eid, vid, name, total, total, cost, image_filename))
            conn.commit(); flash("器材添加成功")
        except Exception as e: conn.rollback(); flash(f"添加失败: {e}")
        finally: conn.close()
        return redirect(url_for("admin_equipment"))

    # GET 请求逻辑 - 原有渲染逻辑保持不变
    try:
        with conn.cursor(DictCursor) as cur:
            # 使用别名确保前端能获取到 ID
            cur.execute("SELECT 器材ID as id, 名称, 总数量, 可用数量, 费用, 图片 FROM 器材")
            items = cur.fetchall()
    finally: conn.close()
    return render_template("admin_equipment.html", user=current_user(), items=items)

# [管理员] 财务图表
@app.get("/admin/finance")
def admin_finance():
    if not admin_required(): return redirect(url_for("login"))
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT DISTINCT DATE_FORMAT(创建时间, '%Y-%m') as m FROM 钱包流水 ORDER BY m DESC")
            month_options = [r['m'] for r in cur.fetchall()]
            
            cur.execute("""
                SELECT 
                    SUM(CASE WHEN 金额 < 0 THEN -金额 ELSE 0 END) as total_income, 
                    SUM(CASE WHEN 金额 > 0 AND 类型='退款' THEN 金额 ELSE 0 END) as total_refund 
                FROM 钱包流水 
                WHERE DATE_FORMAT(创建时间, '%%Y-%%m') = %s
            """, (selected_month,))
            overview = cur.fetchone()

            cur.execute("""
                SELECT f.*, u.姓名, u.学号或工号 
                FROM 钱包流水 f 
                JOIN 钱包账号 w ON f.账户ID=w.账户ID 
                JOIN 用户 u ON w.用户ID=u.用户ID 
                WHERE DATE_FORMAT(f.创建时间, '%%Y-%%m') = %s
                ORDER BY f.创建时间 DESC
            """, (selected_month,))
            flows = cur.fetchall()

            cur.execute("""
                SELECT f.设施类型, COUNT(*) as count 
                FROM 预约记录 r 
                JOIN 场地 f ON r.场地ID=f.场地ID 
                WHERE DATE_FORMAT(r.预约日期, '%%Y-%%m') = %s
                GROUP BY f.设施类型
            """, (selected_month,))
            pie_data = cur.fetchall()
    finally: conn.close()
    return render_template("admin_finance.html", user=current_user(), overview=overview, flows=flows, pie_data=pie_data, month_options=month_options, current_month=selected_month)

# [管理员] 信用管理
@app.route("/admin/credit", methods=["GET", "POST"])
def admin_credit():
    if not admin_required(): return redirect(url_for("login"))
    conn = get_conn()
    if request.method == "POST":
        target_uid = request.form.get("user_id")
        points = int(request.form.get("points", 0))
        reason = request.form.get("reason", "管理员手动扣分")
        try:
            conn.begin()
            with conn.cursor(DictCursor) as cur:
                # 1. 动态寻找一个真实存在的预约ID，规避 1452 约束报错
                cur.execute("SELECT 预约ID FROM 预约记录 LIMIT 1")
                row = cur.fetchone()
                
                if not row:
                    # 如果预约记录表是空的，强制插入一条虚拟占位记录（仅用于满足外键约束）
                    fake_bid = 999999
                    # 随便找一个场地ID和用户ID
                    cur.execute("SELECT 场地ID FROM 场地 LIMIT 1")
                    fid = cur.fetchone()['场地ID']
                    cur.execute("INSERT IGNORE INTO 预约记录 (预约ID, 场地ID, 预约日期, 时间段ID, 预约者id, 组织id, 预约类型, 状态, 创建时间) \
                                 VALUES (%s, %s, CURDATE(), 1, %s, 1, '个人', '已完成', NOW())", (fake_bid, fid, target_uid))
                    valid_bid = fake_bid
                else:
                    valid_bid = row['预约ID']

                # 2. 执行扣分操作
                cur.execute("UPDATE 用户 SET 信用分 = GREATEST(0, 信用分 - %s) WHERE 用户ID = %s", (points, target_uid))
                
                # 3. 插入信用记录，使用刚才找到的 valid_bid
                rid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                cur.execute("""
                    INSERT INTO 信用记录 (信用记录ID, 用户ID, 预约ID, 事件类型, 分数变化, 创建时间) 
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (rid, target_uid, valid_bid, reason, -points))
                
            conn.commit()
            flash("✅ 扣分成功！")
        except Exception as e:
            conn.rollback()
            flash(f"❌ 扣分失败: {str(e)}")
        finally:
            conn.close()
        return redirect(url_for("admin_credit"))

    # 以下是 GET 筛选逻辑（保持你原来的代码逻辑不变）
    try:
        f_score = request.args.get("filter_score")
        sql = "SELECT 用户ID, 学号或工号, 姓名, 信用分, 账号状态 FROM 用户 WHERE 用户类型='学生'"
        if f_score:
            sql += f" AND 信用分 <= {int(f_score)}"
        with conn.cursor(DictCursor) as cur:
            cur.execute(sql + " ORDER BY 信用分 ASC")
            users = cur.fetchall()
    finally:
        conn.close()
    return render_template("admin_credit.html", user=current_user(), users=users, current_filter=f_score)

# [管理员] 删帖
@app.post("/admin/post/delete")
def admin_delete_post():
    if not admin_required(): return redirect(url_for("login"))
    post_id = request.form.get("post_id")
    conn = get_conn()
    try:
        conn.begin()
        with conn.cursor(DictCursor) as cur:
            cur.execute("DELETE FROM 评论 WHERE 帖子id=%s", (post_id,))
            cur.execute("DELETE FROM 帖子 WHERE 帖子id=%s", (post_id,))
        conn.commit(); flash("帖子及评论已永久删除")
    except Exception as e: conn.rollback(); flash(f"删除失败: {e}")
    finally: conn.close()
    return redirect(url_for("community"))

# ================= 学生模块 =================

@app.get("/dashboard")
def dashboard():
    if not login_required(): return redirect(url_for("login"))
    if session.get("role") == "管理员": return redirect(url_for("admin_dashboard"))
    uid = session["user_id"]; conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT u.姓名, u.学号或工号, u.信用分, w.当前余额 FROM 用户 u LEFT JOIN 钱包账号 w ON u.用户ID = w.用户id WHERE u.用户ID = %s", (uid,))
            user_info = cur.fetchone()
    finally: conn.close()
    return render_template("dashboard.html", user=current_user(), info=user_info)

@app.route("/wallet", methods=["GET", "POST"])
def wallet():
    if not login_required(): return redirect(url_for("login"))
    uid = session["user_id"]; conn = get_conn()
    if request.method == "POST":
        try: amount = int(request.form.get("amount", 0))
        except: amount = 0
        if amount > 0:
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    cur.execute("SELECT 账户id, 当前余额 FROM 钱包账号 WHERE 用户id=%s FOR UPDATE", (uid,))
                    w = cur.fetchone()
                    if not w:
                        aid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                        cur.execute("INSERT INTO 钱包账号 (账户id, 用户id, 当前余额) VALUES (%s, %s, 0)", (aid, uid))
                        wid, bal = aid, 0
                    else: wid, bal = w['账户id'], w['当前余额']
                    cur.execute("UPDATE 钱包账号 SET 当前余额=%s WHERE 账户id=%s", (bal+amount, wid))
                    fid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                    cur.execute("INSERT INTO 钱包流水 (流水ID, 账户ID, 预约ID, 金额, 类型, 创建时间) VALUES (%s, %s, %s, %s, '充值', %s)", (fid, wid, None, amount, datetime.now()))
                conn.commit(); flash("充值成功")
            except Exception as e: conn.rollback(); flash(f"失败: {e}")
            finally: conn.close()
        return redirect(url_for("wallet"))
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT 当前余额 FROM 钱包账号 WHERE 用户id=%s", (uid,))
            res = cur.fetchone(); bal = res['当前余额'] if res else 0
            cur.execute("SELECT * FROM 钱包流水 WHERE 账户id=(SELECT 账户id FROM 钱包账号 WHERE 用户id=%s) ORDER BY 创建时间 DESC LIMIT 20", (uid,))
            flows = cur.fetchall()
    finally: conn.close()
    return render_template("wallet.html", user=current_user(), balance=bal, flows=flows)

@app.get("/fields")
def fields():
    if not login_required(): return redirect(url_for("login"))
    campus, fname, ftype = request.args.get("campus",""), request.args.get("venue_name",""), request.args.get("facility","")
    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT DISTINCT 校区 FROM 场馆"); c_opt = [r['校区'] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT 场馆名称 FROM 场馆"); v_opt = [r['场馆名称'] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT 设施类型 FROM 场地"); f_opt = [r['设施类型'] for r in cur.fetchall()]
            sql = "SELECT f.*, v.校区, v.场馆名称, v.图片 FROM 场地 f JOIN 场馆 v ON v.场馆ID=f.场馆ID WHERE 1=1"
            params = []
            if campus: sql+=" AND v.校区=%s"; params.append(campus)
            if ftype: sql+=" AND f.设施类型=%s"; params.append(ftype)
            if fname: sql+=" AND v.场馆名称=%s"; params.append(fname)
            sql += " ORDER BY v.校区, v.场馆名称"
            cur.execute(sql, params); rows = cur.fetchall()
    finally: conn.close()
    return render_template("fields.html", user=current_user(), rows=rows, campus=campus, facility=ftype, venue_name=fname, opt_campuses=c_opt, opt_venues=v_opt, opt_facilities=f_opt)

# [修复] 增加判空检查，防止 TypeError
@app.get("/fields/<int:field_id>/availability")
def availability(field_id):
    if not login_required(): return redirect(url_for("login"))
    d_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    date_val = parse_date(d_str)
    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT * FROM 场地 JOIN 场馆 ON 场地.场馆ID=场馆.场馆ID WHERE 场地ID=%s", (field_id,))
            field = cur.fetchone()
            cur.execute("SELECT * FROM 时间段 ORDER BY 开始时间"); slots = cur.fetchall()
            cur.execute("SELECT 时间段ID FROM 预约记录 WHERE 场地ID=%s AND 预约日期=%s AND 状态 NOT IN ('已取消','自动取消')", (field_id, date_val))
            booked = {r['时间段ID'] for r in cur.fetchall()}
            
            # 精准查询该场地当天的封场记录
            cur.execute("SELECT 开始时间, 结束时间 FROM 封场事件 WHERE 场地ID=%s AND DATE(开始时间)=%s", (field_id, d_str))
            day_blocks = cur.fetchall()

            av_list = []
            for s in slots:
                # 处理时间格式
                s_tm_obj = (datetime.min + s['开始时间']).time()
                s_tm = s_tm_obj.strftime("%H:%M")
                e_tm = (datetime.min + s['结束时间']).time().strftime("%H:%M")
                
                free, reason = True, ""
                if field['状态']!='开放': 
                    free, reason = False, field['状态']
                else:
                    # 检查是否在封场范围内
                    for b in day_blocks:
                        if b['开始时间'].time() <= s_tm_obj < b['结束时间'].time():
                            free, reason = False, "维护/封场"
                            break
                    # 检查是否被预约
                    if free and s['时间段ID'] in booked: 
                        free, reason = False, "已预约"
                
                av_list.append({"slot_id": s['时间段ID'], "start": s_tm, "end": e_tm, "available": free, "reason": reason})
    finally: conn.close()
    return render_template("availability.html", user=current_user(), field=field, date_str=d_str, slots=av_list)

@app.post("/bookings/create")
def create_booking():
    if not login_required(): return redirect(url_for("login"))
    uid, org_id = session["user_id"], session["org_id"]
    fid, date_str, sid, btype = int(request.form.get("field_id")), request.form.get("date"), int(request.form.get("slot_id")), request.form.get("booking_type","个人")
    
    # --- 新增功能：预约时间校验（需求3：只能预约未来一周且不能预约过去的时间） ---
    # 找到原有日期判断逻辑并替换
    try:
        booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = date_cls.today()
        max_date = today + timedelta(days=7) # 未来 7 天
        
        # 核心逻辑：日期必须在 [今天, 今天+7天] 范围内
        if booking_date < today or booking_date > max_date:
            flash(f"❌ 预约失败：仅支持预约今天 ({today}) 至未来七天 ({max_date}) 内的场地。")
            return redirect(url_for("availability", field_id=fid, date=date_str))
    except Exception:
        return redirect(url_for("fields"))
    # -----------------------------------------------------------------------

    bid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
    conn = get_conn()
    try:
        conn.begin()
        with conn.cursor(DictCursor) as cur:
            # 1. 检查信用分
            cur.execute("SELECT 信用分 FROM 用户 WHERE 用户ID=%s", (uid,))
            user_data = cur.fetchone()
            if not user_data or user_data['信用分'] <= 0: raise Exception("信用分不足或归零，无法预约")
            
            # 2. 检查场地状态
            cur.execute("SELECT 预约价格, 状态 FROM 场地 WHERE 场地ID=%s FOR UPDATE", (fid,))
            f_info = cur.fetchone()
            if not f_info: raise Exception("场地不存在")
            if f_info['状态']!='开放': raise Exception("场地当前状态不开放预约")
            
            # 3. 计算价格（判断组织是否免费） 
            price = f_info['预约价格']
            if btype=='组织':
                cur.execute("SELECT 是否免费使用 FROM 组织 WHERE 组织id=%s", (org_id,))
                org_data = cur.fetchone()
                if org_data and org_data['是否免费使用']: price = 0
            
            # 4. 钱包扣费逻辑
            if price > 0:
                cur.execute("SELECT 账户id, 当前余额 FROM 钱包账号 WHERE 用户id=%s FOR UPDATE", (uid,))
                w = cur.fetchone()
                if not w or w['当前余额'] < price: raise Exception("余额不足，请充值")
                
                # 执行扣费
                cur.execute("UPDATE 钱包账号 SET 当前余额=%s WHERE 账户id=%s", (w['当前余额']-price, w['账户id']))
                # 记录流水
                fid_flow = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                cur.execute("INSERT INTO 钱包流水 (流水ID, 账户ID, 预约ID, 金额, 类型, 创建时间) VALUES (%s, %s, %s, %s, '支付', %s)", (fid_flow, w['账户id'], bid, -price, datetime.now()))
            
            # 5. 插入预约记录
            cur.execute("""
                INSERT INTO 预约记录 (预约ID, 场地ID, 预约日期, 时间段ID, 预约者id, 组织id, 预约类型, 状态, 创建时间) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, '已预约', %s)
            """, (bid, fid, date_str, sid, uid, org_id, btype, datetime.now()))
            
            # 6. 如果是组队，添加成员记录（需求1：发起人作为第一个成员）
            if btype=='组队': 
                cur.execute("INSERT INTO 预约成员 VALUES (%s, %s, %s, 1, '已确认', 1)", (bid, datetime.now(), uid))
        
        conn.commit()
        flash("🎉 预约成功！")
        return redirect(url_for("my_bookings"))
    except Exception as e:
        if conn: conn.rollback()
        flash(f"预约失败: {str(e)}")
        return redirect(url_for("availability", field_id=fid, date=date_str))
    finally:
        if conn: conn.close()  

@app.post("/bookings/<int:booking_id>/cancel")
def cancel_booking(booking_id):
    if not login_required(): return redirect(url_for("login"))
    uid = session["user_id"]
    conn = get_conn()
    
    # 获取队员填写的退出原因（如果有）
    cancel_reason = request.form.get("reason", "个人原因取消")
    
    try:
        conn.begin()
        with conn.cursor(DictCursor) as cur:
            # 1. 查找预约的基本信息
            cur.execute("SELECT 预约者id, 状态, 预约日期 FROM 预约记录 WHERE 预约ID=%s", (booking_id,))
            order = cur.fetchone()
            if not order: raise Exception("预约记录不存在")
            if order['状态'] == '已取消': raise Exception("该预约已经是取消状态")

            # 2. 身份判断逻辑
            # 情况 A：当前操作者是【发起人（队长）】或【管理员】 -> 整个订单取消并退款
            if order['预约者id'] == uid or session.get("role") == '管理员':
                # 执行退款逻辑（查询支付流水）
                cur.execute("SELECT 账户id, 当前余额 FROM 钱包账号 WHERE 用户id=%s FOR UPDATE", (order['预约者id'],))
                wallet = cur.fetchone()
                cur.execute("SELECT ABS(金额) as amt FROM 钱包流水 WHERE 预约ID=%s AND 类型='支付' LIMIT 1", (booking_id,))
                payment_flow = cur.fetchone()
                
                if wallet and payment_flow:
                    refund_amt = payment_flow['amt']
                    # 退回钱包
                    cur.execute("UPDATE 钱包账号 SET 当前余额 = 当前余额 + %s WHERE 账户id = %s", (refund_amt, wallet['账户id']))
                    # 插入退款流水
                    rid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                    cur.execute("INSERT INTO 钱包流水 (流水ID, 账户ID, 预约ID, 金额, 类型, 创建时间) VALUES (%s, %s, %s, %s, '退款', %s)", 
                               (rid, wallet['账户id'], booking_id, refund_amt, datetime.now()))
                
                # 更新预约状态为已取消
                cur.execute("UPDATE 预约记录 SET 状态='已取消' WHERE 预约ID=%s", (booking_id,))
                flash(f"✅ 整个预约已取消，费用已退还至发起人钱包")

            # 情况 B：当前操作者是【队员】 -> 仅删除自己的成员记录
            else:
                cur.execute("DELETE FROM 预约成员 WHERE 预约id=%s AND 用户ID=%s", (booking_id, uid))
                # (可选) 你可以在这里记录一下队员取消的原因到日志表，或者这里简单提示
                flash(f"👋 您已成功退出组队。退出原因：{cancel_reason}")
                
        conn.commit()
    except Exception as e:
        if conn: conn.rollback()
        flash(f"❌ 取消失败: {str(e)}")
    finally:
        if conn: conn.close()
        
    return redirect(url_for("my_bookings"))

@app.get("/me/bookings")
def my_bookings():
    if not login_required(): return redirect(url_for("login"))
    # 注意：这里不再限制 role == '学生'，管理员也有 user_id，可以查自己的记录
    uid = session["user_id"]; conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("""
                SELECT r.*, t.开始时间, t.结束时间, f.场地名称, v.校区, v.场馆名称 
                FROM 预约记录 r 
                JOIN 时间段 t ON t.时间段ID = r.时间段ID 
                JOIN 场地 f ON f.场地ID = r.场地ID 
                JOIN 场馆 v ON v.场馆ID = f.场馆ID 
                WHERE r.预约者id = %s OR EXISTS (SELECT 1 FROM 预约成员 m WHERE m.预约id = r.预约ID AND m.用户ID = %s) 
                ORDER BY r.创建时间 DESC LIMIT 50
            """, (uid, uid))
            rows = cur.fetchall()
            # 日历逻辑保持不变
            now = datetime.now(); year, month = now.year, now.month
            month_range = calendar.monthrange(year, month); total_days = month_range[1]; start_weekday = month_range[0] 
            start_date = f"{year}-{month}-01"; end_date = f"{year}-{month}-{total_days}"
            
            # 日历活跃天数也同步修改：我是成员的天数也亮起
            cur.execute("""
                SELECT DISTINCT DAY(预约日期) as day FROM 预约记录 r
                WHERE (r.预约者id=%s OR EXISTS (SELECT 1 FROM 预约成员 m WHERE m.预约id = r.预约ID AND m.用户ID = %s))
                AND r.状态='已预约' AND r.预约日期 >= %s AND r.预约日期 <= %s
            """, (uid, uid, start_date, end_date))
            
            active_days = {row['day'] for row in cur.fetchall()}
            cal_data = {'year': year, 'month': month, 'total_days': total_days, 'start_weekday': start_weekday, 'active_days': active_days, 'count': len(active_days)}
    finally: conn.close()
    return render_template("my_bookings.html", user=current_user(), rows=rows, calendar=cal_data)

@app.route("/bookings/<int:booking_id>/team", methods=["GET", "POST"])
def team_manage(booking_id):
    if not login_required(): return redirect(url_for("login"))
    uid, conn = session["user_id"], get_conn()
    if request.method == "POST":
        sid = request.form.get("student_id", "").strip()
        try:
            conn.begin()
            with conn.cursor(DictCursor) as cur:
                cur.execute("SELECT r.场地ID, f.可容纳人数 FROM 预约记录 r JOIN 场地 f ON r.场地ID=f.场地ID WHERE r.预约ID=%s AND r.预约者id=%s", (booking_id, uid))
                ri = cur.fetchone()
                if not ri: raise Exception("无权操作")
                cur.execute("SELECT COUNT(*) as cc FROM 预约成员 WHERE 预约id=%s", (booking_id,))
                if cur.fetchone()['cc'] >= ri['可容纳人数']: raise Exception(f"人数已满")
                cur.execute("SELECT 用户ID, 姓名 FROM 用户 WHERE 学号或工号=%s", (sid,))
                mem = cur.fetchone()
                if not mem: raise Exception("用户不存在")
                if cur.execute("SELECT 1 FROM 预约成员 WHERE 预约id=%s AND 用户ID=%s", (booking_id, mem['用户ID'])): raise Exception("已在队伍中")
                cur.execute("SELECT MAX(排队序号) as m FROM 预约成员 WHERE 预约id=%s", (booking_id,))
                seq = (cur.fetchone()['m'] or 0) + 1
                cur.execute("INSERT INTO 预约成员 VALUES (%s, %s, %s, %s, '已加入', %s)", (booking_id, datetime.now(), mem['用户ID'], seq, seq))
            conn.commit(); flash(f"已添加: {mem['姓名']}")
        except Exception as e: conn.rollback(); flash(str(e))
        finally: conn.close()
        return redirect(url_for('team_manage', booking_id=booking_id))
    try:
        with conn.cursor(DictCursor) as cur:
            # 核心修复点：使用 JOIN 关联场地表 f，获取真正的场地名称
            cur.execute("""
                SELECT r.*, f.场地名称, f.可容纳人数, v.场馆名称 
                FROM 预约记录 r 
                JOIN 场地 f ON r.场地ID=f.场地ID 
                JOIN 场馆 v ON f.场馆ID=v.场馆ID 
                WHERE r.预约ID=%s
            """, (booking_id,))
            info = cur.fetchone()
            cur.execute("SELECT m.*, u.姓名, u.学号或工号 FROM 预约成员 m JOIN 用户 u ON m.用户ID=u.用户ID WHERE m.预约id=%s ORDER BY m.排队序号", (booking_id,))
            mems = cur.fetchall()
        return render_template("team.html", user=current_user(), booking=info, members=mems)
    except Exception as e: flash(f"加载失败: {e}"); return redirect(url_for('my_bookings'))
    finally: conn.close()

@app.route("/repairs", methods=["GET", "POST"])
def repairs():
    if not login_required(): return redirect(url_for("login"))
    uid, conn = session["user_id"], get_conn()
    if request.method == "POST":
        try:
            conn.begin()
            with conn.cursor(DictCursor) as cur:
                rid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                cur.execute("INSERT INTO 报修单 VALUES (%s, %s, %s, %s, '提交中', %s)", (rid, request.form.get("field_id"), uid, request.form.get("description"), datetime.now()))
            conn.commit(); flash("提交成功")
        except: conn.rollback()
        finally: conn.close()
        return redirect(url_for("repairs"))
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT f.场地ID, f.场地名称, v.场馆名称, v.校区 FROM 场地 f JOIN 场馆 v ON f.场馆ID=v.场馆ID")
            fields = cur.fetchall()
            cur.execute("SELECT r.*, f.场地名称 FROM 报修单 r JOIN 场地 f ON f.场地ID=r.场地ID WHERE r.报修人ID=%s ORDER BY r.创建时间 DESC", (uid,))
            rows = cur.fetchall()
    finally: conn.close()
    return render_template("repairs.html", user=current_user(), fields=fields, rows=rows)

@app.route("/community", methods=["GET", "POST"])
def community():
    if not login_required(): return redirect(url_for("login"))
    uid, conn = session["user_id"], get_conn()
    if request.method == "POST":
        if "delete_post" in request.form and session.get("role") == "管理员": return admin_delete_post()
        t, c, cat = request.form.get("title"), request.form.get("content"), request.form.get("category")
        if t and c:
            try:
                # 拼接标签
                if cat: t = f"[{cat}] {t}"
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    pid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                    cur.execute("INSERT INTO 帖子 VALUES (%s, %s, %s, %s, %s)", (pid, uid, t, c, datetime.now()))
                conn.commit(); flash("发布成功")
            except: conn.rollback()
            return redirect(url_for("community"))
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT p.*, u.姓名, (SELECT COUNT(*) FROM 评论 c WHERE c.帖子id=p.帖子id) as 评论数 FROM 帖子 p JOIN 用户 u ON p.用户id=u.用户ID ORDER BY p.发帖时间 DESC LIMIT 50")
            posts = cur.fetchall()
    finally: conn.close()
    return render_template("community.html", user=current_user(), posts=posts)

@app.route("/community/<int:post_id>", methods=["GET", "POST"])
def post_detail(post_id):
    if not login_required(): return redirect(url_for("login"))
    uid, conn = session["user_id"], get_conn()
    
    if request.method == "POST":
        # 如果是管理员点击了“删除违规贴”按钮
        if "delete_post" in request.form:
             if session.get("role") == "管理员": return admin_delete_post()
        
        # 获取操作类型
        action = request.form.get("action")
        
        try:
            conn.begin()
            with conn.cursor(DictCursor) as cur:
                # 1. 处理点赞
                if action == "like":
                    lid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                    cur.execute("INSERT IGNORE INTO 帖子点赞 (点赞ID, 帖子ID, 用户ID, 创建时间) VALUES (%s, %s, %s, %s)", 
                               (lid, post_id, uid, datetime.now()))
                
                # 2. 处理删除评论
                elif action == "delete_comment":
                    cid = request.form.get("comment_id")
                    cur.execute("DELETE FROM 评论 WHERE 评论id=%s AND (用户id=%s OR %s='管理员')", 
                               (cid, uid, session.get("role")))
                    flash("评论已删除")

                # 3. 处理发表评论 (修正点：确保 action 为 'comment' 或 action 为空时都能发表)
                elif action == "comment" or not action:
                    content = request.form.get("content", "").strip()
                    if content:
                        cid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                        cur.execute("INSERT INTO 评论 VALUES (%s, %s, %s, %s, %s)", (cid, post_id, uid, content, datetime.now()))
                        flash("评论成功")
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f"操作失败: {e}")
        finally:
            conn.close()
        return redirect(url_for("post_detail", post_id=post_id))
    
    # 以下 GET 请求逻辑保持不变
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("SELECT p.*, u.姓名 FROM 帖子 p JOIN 用户 u ON p.用户id=u.用户ID WHERE p.帖子id=%s", (post_id,))
            post = cur.fetchone()
            cur.execute("SELECT c.*, u.姓名 FROM 评论 c JOIN 用户 u ON c.用户id=u.用户ID WHERE c.帖子id=%s ORDER BY c.评论时间", (post_id,))
            comments = cur.fetchall()
            # 统计点赞数以便前端显示
            cur.execute("SELECT COUNT(*) as c FROM 帖子点赞 WHERE 帖子ID=%s", (post_id,))
            likes_count = cur.fetchone()['c']
    finally: conn.close()
    
    if not post: return redirect(url_for("community"))
    return render_template("post_detail.html", user=current_user(), post=post, comments=comments, likes=likes_count)

# [公告] 最终合并修复版：支持发公告、自动批量封场、删除公告并解锁
@app.route("/announcements", methods=["GET", "POST"])
def announcements():
    if not login_required(): return redirect(url_for("login"))
    conn = get_conn()
    
    if request.method == "POST" and session.get("role") == "管理员":
        # 识别操作类型：add (发布) 或 delete (删除)
        action = request.form.get("action", "add")
        
        # ==========================================
        # 1. 发布公告逻辑 (区分通知与封场)
        # ==========================================
        if action == "add":
            title = request.form.get("title")
            content = request.form.get("content")
            type_ = request.form.get("type", "通知")
            field_id = request.form.get("field_id") 
            block_date = request.form.get("block_date")
            st, et = request.form.get("start_time"), request.form.get("end_time")
            
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    # 获取系统内真实场地 ID 满足数据库非空约束
                    cur.execute("SELECT 场馆ID, 场地ID FROM 场地 LIMIT 1")
                    placeholder = cur.fetchone()
                    if not placeholder:
                        flash("❌ 失败：系统中没有任何场地")
                        return redirect(url_for("announcements"))
                    
                    real_vid = placeholder['场馆ID']
                    real_fid = placeholder['场地ID'] 
                    aid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                    
                    # --- 情况 A：纯校园通知 (不提示封锁) ---
                    if type_ == "通知":
                        sql = """
                            INSERT INTO 公告 (公告ID, 场馆ID, 场地ID, 公告类型, 标题, 内容, 开始时间, 发布人id) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cur.execute(sql, (aid, real_vid, real_fid, '通知', title, content, datetime.now(), session["user_id"]))
                        flash("✅ 校园通知发布成功")
                    
                    # --- 情况 B：封场/维修/赛事 (执行时段锁定) ---
                    else:
                        if not (block_date and st and et):
                            flash("❌ 封场类公告必须填写日期和时段")
                            return redirect(url_for("announcements"))
                        
                        s_dt, e_dt = f"{block_date} {st}:00", f"{block_date} {et}:00"
                        
                        # 拼接时段至内容，激活前端红色条显示
                        full_content = f"{content} (时间: {block_date} {st} 至 {et})"
                        
                        # 判断全馆封锁还是单场封锁
                        if field_id:
                            target_fields = [{'fid': field_id, 'vid': real_vid}]
                        else:
                            title = f"【全馆封锁】{title}"
                            cur.execute("SELECT 场地ID, 场馆ID FROM 场地")
                            target_fields = [{'fid': r['场地ID'], 'vid': r['场馆ID']} for r in cur.fetchall()]

                        # 循环插入封场事件，让预约页面显示“维护中”
                        for idx, item in enumerate(target_fields):
                            eid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]) + idx
                            cur.execute("""
                                INSERT INTO 封场事件 (封场ID, 场馆ID, 场地ID, 开始时间, 结束时间, 原因类型) 
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (eid, item['vid'], item['fid'], s_dt, e_dt, type_))
                        
                        # 插入公告显示记录
                        sql_ann = """
                            INSERT INTO 公告 (公告ID, 场馆ID, 场地ID, 公告类型, 标题, 内容, 开始时间, 发布人id) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cur.execute(sql_ann, (aid, real_vid, (field_id if field_id else real_fid), type_, title, full_content, datetime.now(), session["user_id"]))
                        flash("✅ 公告发布成功，已同步封锁对应时段")
                
                conn.commit()
            except Exception as e:
                conn.rollback()
                flash(f"❌ 发布失败: {str(e)}")
            return redirect(url_for("announcements"))

        # ==========================================
        # 2. 删除公告逻辑 (同步解锁场地)
        # ==========================================
        elif action == "delete":
            aid = request.form.get("announcement_id")
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    # 1. 提取公告，识别是否涉及封场
                    cur.execute("SELECT 场地ID, 内容 FROM 公告 WHERE 公告ID=%s", (aid,))
                    target = cur.fetchone()
                    
                    if target:
                        # 2. 如果是带时间段的公告，删除封场表中的拦截记录以解锁场地
                        if "(时间:" in target['内容']:
                            # 为了精准解锁，这里删除该场地关联的封场记录
                            cur.execute("DELETE FROM 封场事件 WHERE 场地ID=%s AND 原因类型 != '通知'", (target['场地ID'],))
                        
                        # 3. 删除公告本体
                        cur.execute("DELETE FROM 公告 WHERE 公告ID=%s", (aid,))
                
                conn.commit()
                flash("✅ 公告已成功删除，相关场地已解锁")
            except Exception as e:
                conn.rollback()
                flash(f"❌ 删除失败: {str(e)}")
            return redirect(url_for("announcements"))

    # ==========================================
    # 3. GET 请求：数据查询与渲染逻辑
    # ==========================================
    try:
        with conn.cursor(DictCursor) as cur:
            # 查询公告列表
            cur.execute("""
                SELECT g.*, v.校区, v.场馆名称, f.场地名称, u.姓名 as 发布人 
                FROM 公告 g 
                LEFT JOIN 场馆 v ON g.场馆ID = v.场馆ID 
                LEFT JOIN 场地 f ON g.场地ID = f.场地ID 
                LEFT JOIN 用户 u ON g.发布人id = u.用户ID 
                ORDER BY g.开始时间 DESC LIMIT 20
            """)
            rows = cur.fetchall()
            # 查询场地选项用于发布表单
            cur.execute("SELECT f.场地ID, f.场地名称, v.场馆名称, v.校区 FROM 场地 f JOIN 场馆 v ON f.场馆ID=v.场馆ID ORDER BY v.校区")
            fields = cur.fetchall()
            return render_template("announcements.html", user=current_user(), rows=rows, fields=fields)
    finally: conn.close()
    
# [器材] 修复版：使用别名(id,name...)防止空指针
@app.route("/equipments", methods=["GET", "POST"])
def equipments():
    if not login_required(): return redirect(url_for("login"))
    uid, conn = session["user_id"], get_conn()
    if request.method == "POST":
        action = request.form.get("action")
        # 归还
        if action == "return":
            bid = request.form.get("borrow_id")
            try:
                conn.begin()
                with conn.cursor(DictCursor) as cur:
                    cur.execute("SELECT * FROM 器材借用 WHERE 借用id=%s FOR UPDATE", (bid,))
                    rec = cur.fetchone()
                    if rec and rec['状态'] == '借出':
                        cur.execute("UPDATE 器材借用 SET 状态='已还' WHERE 借用id=%s", (bid,))
                        cur.execute("UPDATE 器材 SET 可用数量=可用数量+1 WHERE 器材id=%s", (rec['器材id'],))
                        conn.commit(); flash("✅ 归还成功")
            except Exception as e: conn.rollback(); flash(f"归还失败: {e}")
            finally: conn.close()
            return redirect(url_for("equipments"))
        
        # 借用
        eq_id = request.form.get("eq_id")
        try:
            conn.begin()
            with conn.cursor(DictCursor) as cur:
                # 使用标准查询，防止字段名不匹配
                cur.execute("SELECT 器材ID, 可用数量, 费用 FROM 器材 WHERE 器材ID=%s FOR UPDATE", (eq_id,))
                eq = cur.fetchone()
                
                if not eq: raise Exception("器材不存在")
                if eq['可用数量'] <= 0: raise Exception("库存不足")
                cost = eq['费用']
                
                cur.execute("SELECT 账户id, 当前余额 FROM 钱包账号 WHERE 用户id=%s FOR UPDATE", (uid,))
                w = cur.fetchone()
                if not w or w['当前余额'] < cost: raise Exception("余额不足")
                
                cur.execute("UPDATE 器材 SET 可用数量=可用数量-1 WHERE 器材ID=%s", (eq_id,))
                cur.execute("UPDATE 钱包账号 SET 当前余额=当前余额-%s WHERE 账户id=%s", (cost, w['账户id']))
                
                bid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                cur.execute("INSERT INTO 器材借用 (借用id, 器材id, 借用人id, 借出时间, 状态) VALUES (%s, %s, %s, %s, '借出')", (bid, eq_id, uid, datetime.now()))
                
                fid = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
                cur.execute("INSERT INTO 钱包流水 (流水ID, 账户ID, 预约ID, 金额, 类型, 创建时间) VALUES (%s, %s, %s, %s, '器材费', %s)", (fid, w['账户id'], None, -cost, datetime.now()))
            conn.commit(); flash("✅ 借用成功")
        except Exception as e: conn.rollback(); flash(f"失败: {e}")
        finally: conn.close()
        return redirect(url_for("equipments"))
    
    # GET展示
    try:
        with conn.cursor(DictCursor) as cur:
            # 统一使用别名
            cur.execute("SELECT 器材ID as id, 名称 as name, 总数量 as total, 可用数量 as available, 费用 as cost, 图片 as image FROM 器材")
            items = cur.fetchall()
            
            cur.execute("""
                SELECT b.借用ID as borrow_id, q.名称 as name, b.借出时间 as time, b.状态 as status 
                FROM 器材借用 b JOIN 器材 q ON b.器材id=q.器材id 
                WHERE b.借用人id=%s ORDER BY b.借出时间 DESC
            """, (uid,))
            my_items = cur.fetchall()
    finally: conn.close()
    return render_template("equipments.html", user=current_user(), items=items, my_items=my_items)

# 临时工具：用于补全数据库时间段和修复封场逻辑
@app.route("/admin/fix_db_data")
def fix_db_data():
    if not admin_required():
        return "请先以管理员身份登录", 403
    
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 补全缺失的时间段 (需求 5)
            # 使用 INSERT IGNORE 防止重复执行报错
            sql_slots = """
            INSERT IGNORE INTO 时间段 (时间段ID, 开始时间, 结束时间) VALUES 
            (20, '11:00:00', '12:00:00'),
            (21, '12:00:00', '13:00:00'),
            (22, '13:00:00', '14:00:00'),
            (23, '16:00:00', '17:00:00'),
            (24, '17:00:00', '18:00:00'),
            (25, '18:00:00', '19:00:00'),
            (26, '20:00:00', '21:00:00');
            """
            cur.execute(sql_slots)
            
            # 2. 检查封场事件表结构（确保支持精确时间）
            # 这一步是为了防止你之前的表结构只有日期没有时间
            cur.execute("ALTER TABLE 封场事件 MODIFY COLUMN 开始时间 DATETIME;")
            cur.execute("ALTER TABLE 封场事件 MODIFY COLUMN 结束时间 DATETIME;")
            
        conn.commit()
        return "<h1>✅ 数据库修复成功！</h1><p>时间段已补全，封场表结构已优化。</p><a href='/'>返回首页</a>"
    except Exception as e:
        return f"<h1>❌ 执行失败</h1><p>{str(e)}</p>"
    finally:
        conn.close()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)