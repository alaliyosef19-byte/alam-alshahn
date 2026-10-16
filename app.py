from dotenv import load_dotenv; load_dotenv()
import time
import os,sqlite3,uuid,requests
from flask import Flask,request,jsonify,render_template,session
from werkzeug.security import generate_password_hash,check_password_hash

app=Flask(__name__)
app.secret_key=os.getenv("SECRET_KEY","change-this-secret")
DB=os.getenv("DATABASE_PATH","database.db")
BASE=os.getenv("SHAM4STORE_BASE_URL","https://api.sham4store.com").rstrip("/")

PRODUCT_CACHE = None
PRODUCT_CACHE_AT = 0
CACHE_TTL = 90
KEY=os.getenv("SHAM_STORE_API_TOKEN","")
ADMIN=os.getenv("ADMIN_USER","admin")
ADMIN_PASS=os.getenv("ADMIN_PASSWORD","admin123")
CACHE={"time":0,"products":[]}

def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c

def init():
 c=db()
 c.executescript("""
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,password TEXT,balance REAL DEFAULT 0,is_admin INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,product_id INTEGER,name TEXT,price REAL,player TEXT,qty INTEGER,status TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS deposits(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount REAL,method TEXT,proof TEXT,status TEXT DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,message TEXT,reply TEXT DEFAULT '',status TEXT DEFAULT 'open',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS price_overrides(product_id INTEGER PRIMARY KEY,price REAL);
 """)
 if not c.execute("SELECT id FROM users WHERE username=?",(ADMIN,)).fetchone():
  c.execute("INSERT INTO users(username,password,balance,is_admin) VALUES(?,?,0,1)",(ADMIN,generate_password_hash(ADMIN_PASS)))
 c.commit();c.close()
init()

def headers(): return {"api-token":KEY,"Accept":"application/json"}

def products():
    global PRODUCT_CACHE, PRODUCT_CACHE_AT
    now=time.time()

    if PRODUCT_CACHE is not None and now-PRODUCT_CACHE_AT < CACHE_TTL:
        return PRODUCT_CACHE

    r=requests.get(
        BASE+"/client/api/products",
        headers=headers(),
        timeout=30
    )
    r.raise_for_status()
    data=r.json()
    PRODUCT_CACHE=data if isinstance(data,list) else []
    PRODUCT_CACHE_AT=now
    return PRODUCT_CACHE

def price(p):
    # سعر Sham4Store + هامش ربح 2%
    try:
        base = float(p.get("price") or 0)
    except:
        base = 0.0

    try:
        c = db()
        x = c.execute(
            "SELECT price FROM price_overrides WHERE product_id=?",
            (str(p.get("id")),)
        ).fetchone()
        c.close()
        if x:
            base = float(x["price"])
    except:
        pass

    return round(base * 1.02, 2)

def user():
 if not session.get("uid"):return None
 c=db();x=c.execute("SELECT id,username,balance,is_admin FROM users WHERE id=?",(session["uid"],)).fetchone();c.close()
 return dict(x) if x else None

@app.get("/")
def home():return render_template("index.html")

@app.get("/api/me")
def me():return jsonify(ok=True,user=user())

@app.post("/api/register")
def register():
    d=request.json or {}
    u=str(d.get("username","")).strip()
    pw=str(d.get("password",""))

    if len(u)<3:
        return jsonify(ok=False,message="اسم المستخدم يجب أن يكون 3 أحرف على الأقل"),400
    if len(pw)<4:
        return jsonify(ok=False,message="كلمة المرور يجب أن تكون 4 أحرف على الأقل"),400

    c=db()
    try:
        old=c.execute("SELECT id FROM users WHERE username=?",(u,)).fetchone()
        if old:
            return jsonify(ok=False,message="هذا الاسم مستخدم بالفعل، استخدم تسجيل الدخول"),409

        c.execute(
            "INSERT INTO users(username,password,balance,is_admin) VALUES(?,?,0,0)",
            (u,generate_password_hash(pw))
        )
        c.commit()
        row=c.execute("SELECT id,username,balance,is_admin FROM users WHERE username=?",(u,)).fetchone()
        session["uid"]=row["id"]
        return jsonify(ok=True,success=True,message="تم إنشاء الحساب بنجاح",user=dict(row))
    except Exception as e:
        c.rollback()
        return jsonify(ok=False,message="تعذر إنشاء الحساب: "+str(e)),500
    finally:
        c.close()

@app.post("/api/login")
def login():
 d=request.json or {};c=db();x=c.execute("SELECT * FROM users WHERE username=?",(str(d.get("username","")).strip(),)).fetchone();c.close()
 if not x or not check_password_hash(x["password"],str(d.get("password",""))):return jsonify(ok=False,message="بيانات الدخول غير صحيحة"),401
 session["uid"]=x["id"];return jsonify(ok=True)

@app.post("/api/logout")
def logout():session.clear();return jsonify(ok=True)

# تصنيف المنتجات إلى أقسام المتجر
def section_for(p):
    n=str(p.get("name") or "").upper()
    c=str(p.get("category_name") or p.get("category") or "").upper()
    text=n+" "+c

    if "FC POINTS" in text:
        return "excluded"

    # الألعاب
    games=[
        "PUBG","FREE FIRE","CALL OF DUTY","COD MOBILE",
        "8BALL","BRAWL STARS","CLASH OF CLANS","HAY DAY",
        "FARM PASS","MIXU","BERMUDA","WAR ROBOTS"
    ]
    if any(x in text for x in games):
        return "games"

    # تطبيقات اللايف
    live=[
        "YALLA","LUDO","LIVU","TUMILE","BIGO","POPPO",
        "HAGO","MEYO","SUGO","STAR MAKER","LIKEE",
        "LEESKI","IMO","AZAR","NIMO","MICO","HIGO","MIGO",
        "YOYO","YOHO","TAMI","OOHLA","HEYA","FANCY","AYOME",
        "WYAK","COCCO","FALLA","AHLAN","HABBY","KIYO","LIGO",
        "LIGHT","NABD","TAKA","SABA","DIMO","ASWAT","LAMI",
        "SPARTY","BEELA","BOBO","GOMEET","HAWA","SOULFA",
        "TANGO","MANGO","PAWA","DANA","OPA","KITI","LADO",
        "SAADA","HALLA","HATI","VILAA","UPLIVE","GAMET",
        "XENA","SODFA","TADA","ALLO","WAHO","SANGO","POTA",
        "WAAW","GIMME","HAKI","SALAM","HIYA","LAYLA","ECHO",
        "HABI","HOOB","LAMA","YAAHLAN","MR7BA","PEP","HOBY"
    ]
    if any(x in text for x in live):
        return "live"

    chat_live_words=[
        "CHAT","LIVE","PARTY","LIVU","BIGO","POPPO","TUMILE","YALLA",
        "MEYO","SUGO","LIKEE","IMO","AZAR","HAGO","NIMO","MICO",
        "HIGO","MIGO","YOYO","YOHO","TAMI","OOHLA","HEYA","FANCY",
        "AYOME","WYAK","COCCO","FALLA","AHLAN","HABBY","KIYO","LIGO",
        "LIGHT","NABD","TAKA","SABA","DIMO","ASWAT","LAMI","SPARTY",
        "BEELA","BOBO","GOMEET","HAWA","SOULFA","TANGO","MANGO","PAWA",
        "DANA","OPA","KITI","LADO","SAADA","HALLA","HATI","VILAA",
        "UPLIVE","GAMET","XENA","SODFA","TADA","ALLO","WAHO","SANGO",
        "POTA","WAAW","GIMME","HAKI","SALAM","HIYA","LAYLA","ECHO",
        "HABI","HOOB","LAMA","YAAHLAN","MR7BA","PEP","HOBY","PARTY"
    ]
    if any(x in text for x in chat_live_words):
        return "live"

    # الاتصالات
    telecom=[
        "SYRIATEL","SYRIA TEL","MTN SYRIA","MTN",
        "MTC","ALFA","FSN","SPACETEL","TELECOM SYRIA"
    ]
    if any(x in text for x in telecom):
        return "telecom"

    # التفعيل
    activation=[
        "NETFLIX","SHAHID","SHAHED","SHAMNA","IPTV"
    ]
    if any(x in text for x in activation):
        return "activation"

    # المتاجر الرقمية
    stores=[
        "ITUNES","APPLE","GOOGLE PLAY","STEAM",
        "PLAYSTATION","PSN","XBOX","RAZER","STORE"
    ]
    if any(x in text for x in stores):
        return "stores"

    return "other"

@app.get("/api/categories")
def categories():
    p=products()
    names={
        "games":"🎮 الألعاب",
        "live":"📱 تطبيقات اللايف",
        "telecom":"📡 الاتصالات",
        "activation":"🔑 التفعيل",
        "stores":"🛒 المتاجر الرقمية"
    }
    counts={x:0 for x in names}
    for x in p:
        sec=section_for(x)
        if sec in counts:
            counts[sec]+=1
    return jsonify(ok=True,categories=[
        {"id":k,"name":names[k],"count":counts[k]}
        for k in names
    ])

@app.get("/api/apps")
def apps():
    section=str(request.args.get("section","games")).strip().lower()
    try:
        limit=min(max(int(request.args.get("limit",50)),1),500)
    except:
        limit=50
    try:
        offset=max(int(request.args.get("offset",0)),0)
    except:
        offset=0

    groups={}
    aliases={
        "PUBG GLOBAL OTOMATIK":"PUBG GLOBAL OTOMATIK",
        "PUBG GLOBAL":"PUBG GLOBAL",
        "PUBG MOBILE":"PUBG MOBILE",
        "FREE FIRE":"FREE FIRE",
        "CALL OF DUTY":"CALL OF DUTY MOBILE",
        "8BALL":"8BALL POOL",
        "BRAWL STARS":"BRAWL STARS",
        "CLASH OF CLANS":"CLASH OF CLANS",
        "HAY DAY":"HAY DAY",
        "FARM PASS":"FARM PASS",
        "WAR ROBOTS":"WAR ROBOTS",
        "YALLA LIVE":"YALLA LIVE",
        "YALLA LUDO":"YALLA LUDO",
        "LIVU":"LIVU",
        "LEVU":"LIVU",
        "TUMILE":"TUMILE",
        "BIGO":"BIGO LIVE",
        "POPPO":"POPPO",
        "HAGO":"HAGO",
        "MEYO":"MEYO",
        "SUGO":"SUGO",
        "STAR MAKER":"STAR MAKER",
        "LIKEE":"LIKEE",
        "LEESKI":"LEESKI",
        "IMO":"IMO",
        "LUDO":"LUDO",
        "ITUNES":"ITUNES",
        "APPLE":"APPLE",
        "GOOGLE":"GOOGLE",
        "STEAM":"STEAM",
        "PLAYSTATION":"PLAYSTATION",
        "PSN":"PLAYSTATION",
        "XBOX":"XBOX",
        "RAZER":"RAZER",
        "SYRIATEL":"SYRIATEL",
        "MTN":"MTN",
        "MTC":"MTC",
        "NETFLIX":"NETFLIX",
        "SHAHID":"SHAHID",
        "SHAHED":"SHAHED",
        "SHAMNA":"SHAMNA TV",
        "IPTV":"IPTV"
    }

    def image_of(p):
        for k in ("image","category_img"):
            v=str(p.get(k) or "").strip()
            if v.startswith(("http://","https://")) and v.rstrip("/") not in ("https://api.sham4store.com","http://api.sham4store.com"):
                return v
        return ""

    def app_name(p):
        text=(str(p.get("category_name") or "")+" "+str(p.get("name") or "")).upper()
        for needle,title in aliases.items():
            if needle in text:
                return title
        return str(p.get("category_name") or "").strip()

    for pdt in products():
        if section_for(pdt)!=section:
            continue

        try:
            pid=int(pdt.get("id"))
        except:
            continue

        if section=="live":
            raw=str(pdt.get("category_name") or "").strip()
            title=raw
            # لا نخلط مجموعات الباقات المختلفة لنفس التطبيق
            current_parent=pdt.get("parent_id")
            upper=raw.upper()
            canonical={
                "BIGO":"BIGO LIVE","BIGO LIVE":"BIGO LIVE",
                "MEYO":"MEYO","MEYO CHAT":"MEYO","MEYO LIVE":"MEYO",
                "IMO":"IMO","IMO CHAT":"IMO",
                "FALLA":"FALLA","FALLA CHAT":"FALLA",
                "LIKEE":"LIKEE","LIKEE LIVE":"LIKEE","SAYA LIKEE":"LIKEE",
                "TUMILE":"TUMILE","TUMILE LIVE":"TUMILE",
                "HIGO":"HIGO","HIGO LIVE":"HIGO","HIGO CHAT":"HIGO",
                "MIGO":"MIGO","MIGO LIVE":"MIGO","MIGO CHAT":"MIGO",
                "LUDO DIAMONDS":"LUDO DIAMONDS",
                "YALLA LIVE":"YALLA LIVE",
                "POPPO LIVE":"POPPO","POPPO":"POPPO",
                "NIMO TV":"NIMO TV","SUGO LITE":"SUGO LITE",
                "TANGO LIVE":"TANGO LIVE","MANGO LIVE":"MANGO LIVE",
                "PAWA LIVE":"PAWA LIVE","UPLIVE":"UPLIVE",
                "AZAR":"AZAR","AZAR CHAT":"AZAR",
                "HAGO":"HAGO","HAGO CHAT":"HAGO",
                "LIVU":"LIVU","LEESKI":"LEESKI"
            }
            if upper in canonical:
                title=canonical[upper]
            elif upper.endswith(" CHAT"):
                title=upper[:-5].strip()
            elif upper.endswith(" LIVE"):
                title=upper[:-5].strip()
            excluded={
                "قسم التطبيقات","WORLD OF APPLICATIONS","APPLICATION SHIPPING",
                "APPS SECTION","APPLICATIONS","APLLICATIONS","APPLICATION NUMBERS",
                "YALLA LUDO GOLD","YALLA LUDO GOLD دهب",
                "YALLA LUDO DIAMONDS","LUDO DIAMONDS","LUDO CLUB",
                "LUDO CLUB COINS","LUDO CLUB CASH","LUDO WORLD",
                "FARLIGHT 84","FARLIGHT","MOBILE LEGENDS"
            }
            if not title or upper in excluded:
                continue
            if title.strip().upper() in {"CHATGPT", "CHATGPT - GO", "CHATGPT GO", "CHAT APPLICATIONS"}:
                continue
            if not any(x in upper for x in (
                "LIVE","CHAT","LIVU","BIGO","POPPO","TUMILE","YALLA",
                "MEYO","SUGO","LIKEE","LEESKI","IMO","AZAR","HAGO",
                "NIMO","MICO","HIGO","MIGO","YOYO","YOHO","TAMI",
                "OOHLA","HEYA","FANCY","AYOME","WYAK","COCCO","FALLA",
                "AHLAN","HABBY","KIYO","LIGO","LIGHT","NABD","TAKA",
                "SABA","DIMO","ASWAT","LAMI","SPARTY","BEELA","BOBO",
                "GOMEET","HAWA","SOULFA","TANGO","MANGO","PAWA","DANA",
                "OPA","KITI","LADO","Laki","SAADA","HALLA","HATI","VILAA",
                "UPLIVE","GAMET"
            )):
                continue
        else:
            title=app_name(pdt)
            if not title:
                continue
        if section=="games" and title.strip().upper() in {"مكس يو","MIXU","FARM PASS"}:
            continue

        # عرض FARM PASS ضمن باقات HAY DAY بدل إنشاء كرت مستقل
        if section=="games" and "HAY DAY" in (
            str(pdt.get("name") or "").upper() + " " +
            str(pdt.get("category_name") or "").upper()
        ):
            title="HAY DAY"
        if section=="stores" and title.strip().upper() in {"APPLICATIONS", "المتاجر الرقمية"}:
            continue

        if section=="telecom":
            tn=str(pdt.get("name") or "").upper()
            tc=str(pdt.get("category_name") or "").upper()
            telecom_name=title.upper()
            if telecom_name=="ALFA" and any(x in tn for x in ("MTC","MTN","SYRIATEL","FSN")):
                continue
            if telecom_name=="MTC" and any(x in tn for x in ("ALFA","MTN","SYRIATEL","FSN")):
                continue
            if telecom_name=="MTN" and any(x in tn for x in ("ALFA","MTC","SYRIATEL","FSN")):
                continue
            if telecom_name=="SYRIATEL" and any(x in tn for x in ("ALFA","MTC","MTN","FSN")):
                continue
            if telecom_name=="FSN" and any(x in tn for x in ("ALFA","MTC","MTN","SYRIATEL")):
                continue

        if section=="games":
            bad={
                "BERMUDA","GLOBAL PUBG","PUBG OTOMATIK","PUBG MANUAL",
                "PUBG CODES","PUBG SERVER (1)","PUBG SERVER (2)","SERVER (3)",
                "PUBG TR","PUBG TR التركية","PUBG عالمي اوتماتيك",
                "TURKISH PUBG","ببجي عالمي","PUBG NEW STATE","PUBG MOBail | TR"
            }
            if title.upper() in bad:
                continue

        if section=="games" and "PUBG" in title.upper():
            if title.upper()!="PUBG GLOBAL OTOMATIK":
                continue
            title="PUBG GLOBAL OTOMATIK"
        title_key = " ".join(title.upper().split())
        display_title = title
        key = title_key

        if key not in groups:
            groups[key]={
                "name":display_title,
                "image":image_of(pdt),
                "parent_id":pdt.get("parent_id"),
                "products":[],
                "_seen":set()
            }

        g=groups[key]

        pname=str(pdt.get("name") or "").strip()
        pkey="|".join([
            " ".join(pname.upper().split()),
            str(pdt.get("product_type") or "").upper().strip(),
            "|".join(str(x).strip().upper() for x in (pdt.get("params") or [])),
            str(pdt.get("price") if pdt.get("price") is not None else "").strip(),
            repr(pdt.get("qty_values") or []),
            str(pdt.get("parent_id") if pdt.get("parent_id") is not None else "").strip()
        ])
        if pkey not in g["_seen"]:
            g["_seen"].add(pkey)
            g["products"].append({
                "id":pid,
                "name":pname,
                "parent_id":pdt.get("parent_id"),
                "product_type":pdt.get("product_type"),
                "params":pdt.get("params") or []
            })

        if not g["image"]:
            g["image"]=image_of(pdt)

    for g in groups.values():
        if g["name"]=="PUBG MOBILE":
            g["products"]=g["products"][-6:]

    result=[]
    for g in groups.values():
        g.pop("_seen",None)
        if g["products"]:
            result.append(g)

    if section=="games":
        order=["PUBG GLOBAL OTOMATIK","PUBG GLOBAL","PUBG MOBILE","FREE FIRE","CALL OF DUTY MOBILE","8BALL POOL","BRAWL STARS","CLASH OF CLANS","HAY DAY","FARM PASS","WAR ROBOTS"]
    elif section=="live":
        order=["YALLA LIVE","YALLA LUDO","LIVU","TUMILE","BIGO LIVE","POPPO","HAGO","MEYO","SUGO","STAR MAKER","LIKEE","LEESKI","IMO","LUDO"]
    else:
        order=[]

    result.sort(key=lambda x:(order.index(x["name"].upper()) if x["name"].upper() in order else 999,x["name"].upper()))

    page=result[offset:offset+limit]

    return jsonify(
        ok=True,
        apps=page,
        total=len(result),
        limit=limit,
        offset=offset,
        has_more=offset+limit<len(result)
    )

@app.get("/api/app-packages")
def app_packages():
    try:
        ids=str(request.args.get("ids","")).split(",")
        ids={int(x) for x in ids if x.strip().isdigit()}

        if not ids:
            return jsonify(ok=True,packages=[])

        out=[]

        for p in products():
            try:
                pid=int(p.get("id"))
            except Exception:
                continue

            if pid not in ids:
                continue

            x=dict(p)
            x["store_price"]=price(p)
            out.append(x)

        return jsonify(ok=True,packages=out)

    except Exception as e:
        return jsonify(ok=False,error=str(e),packages=[]),500

@app.get("/api/packages/<int:product_id>")
def packages(product_id):
    try:
        x=product_details(product_id)
        if not x:
            return jsonify(ok=True,packages=[])

        x=dict(x)
        x["store_price"]=price(x)

        return jsonify(ok=True,packages=[x])
    except Exception as e:
        return jsonify(ok=False,error=str(e),packages=[]),500

@app.get("/api/products")
def api_products():
    q=str(request.args.get("q","")).lower().strip()
    cat=str(request.args.get("category","")).strip()
    section=str(request.args.get("section","")).strip()

    out=[]
    for p in products():
        n=str(p.get("name",""))
        c=str(p.get("category_name") or p.get("category") or "أخرى")

        if cat and c!=cat:
            continue
        if section and section_for(p)!=section:
            continue
        if q and q not in n.lower():
            continue

        x=dict(p)
        x["store_price"]=price(p)
        x["category"]=c
        x["section"]=section_for(p)
        out.append(x)

    return jsonify(ok=True,products=out,total=len(out))

@app.post("/api/order")
def order():
 u=user()
 if not u:return jsonify(ok=False,message="يجب تسجيل الدخول"),401
 d=request.json or {};pid=int(d.get("product_id",0));qty=max(1,int(d.get("quantity",1)));player=str(d.get("player_id","")).strip()
 p=next((x for x in products() if int(x.get("id",-1))==pid),None)
 if not p:return jsonify(ok=False,message="الباقة غير موجودة"),404
 total=price(p)*qty
 if total<=0:return jsonify(ok=False,message="سعر الباقة غير صحيح"),400
 if u["balance"]<total:return jsonify(ok=False,message=f"الرصيد غير كافٍ. المطلوب {total:.2f}$"),400
 try:
  r=requests.get(BASE+f"/client/api/newOrder/{pid}/params",params={"qty":qty,"playerId":player,"order_uuid":str(uuid.uuid4())},headers=headers(),timeout=30)
  result=r.json();ok=result.get("status") is True or result.get("success") is True
  if not ok:return jsonify(ok=False,message=result.get("message","فشل تنفيذ الطلب")),400
  c=db();c.execute("UPDATE users SET balance=balance-? WHERE id=?",(total,u["id"]));c.execute("INSERT INTO orders(user_id,product_id,name,price,player,qty,status) VALUES(?,?,?,?,?,?,?)",(u["id"],pid,p.get("name",""),total,player,qty,"success"));c.commit();c.close()
  return jsonify(ok=True,message="تم تنفيذ الطلب بنجاح")
 except Exception as e:return jsonify(ok=False,message="تعذر الاتصال بخدمة الشحن"),502

@app.get("/api/orders")
def orders():
 u=user()
 if not u:return jsonify(ok=False),401
 c=db();x=c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall();c.close()
 return jsonify(ok=True,orders=[dict(a) for a in x])

@app.post("/api/deposit")
def deposit():
 u=user()
 if not u:return jsonify(ok=False,message="يجب تسجيل الدخول"),401
 d=request.json or {}
 try:a=float(d.get("amount",0))
 except:a=0
 if a<=0:return jsonify(ok=False,message="المبلغ غير صحيح"),400
 c=db();c.execute("INSERT INTO deposits(user_id,amount,method,proof) VALUES(?,?,?,?)",(u["id"],a,str(d.get("method","")),str(d.get("proof",""))));c.commit();c.close()
 return jsonify(ok=True,message="تم إرسال طلب الإيداع")

@app.post("/api/support")
def support():
 u=user()
 if not u:return jsonify(ok=False),401
 m=str((request.json or {}).get("message","")).strip()
 if not m:return jsonify(ok=False,message="اكتب الرسالة"),400
 c=db();c.execute("INSERT INTO tickets(user_id,message) VALUES(?,?)",(u["id"],m));c.commit();c.close();return jsonify(ok=True)

def admin():
 u=user();return u and u["is_admin"]

@app.get("/api/admin")
def admin_data():
 if not admin():return jsonify(ok=False),403
 c=db()
 d=c.execute("SELECT deposits.*,users.username FROM deposits JOIN users ON users.id=deposits.user_id ORDER BY deposits.id DESC").fetchall()
 o=c.execute("SELECT orders.*,users.username FROM orders JOIN users ON users.id=orders.user_id ORDER BY orders.id DESC").fetchall()
 t=c.execute("SELECT tickets.*,users.username FROM tickets JOIN users ON users.id=tickets.user_id ORDER BY tickets.id DESC").fetchall()
 c.close();return jsonify(ok=True,deposits=[dict(x) for x in d],orders=[dict(x) for x in o],tickets=[dict(x) for x in t])

@app.post("/api/admin/deposit/<int:i>")
def approve(i):
 if not admin():return jsonify(ok=False),403
 a=(request.json or {}).get("action");c=db();d=c.execute("SELECT * FROM deposits WHERE id=?",(i,)).fetchone()
 if not d or d["status"]!="pending":c.close();return jsonify(ok=False),400
 if a=="approve":c.execute("UPDATE users SET balance=balance+? WHERE id=?",(d["amount"],d["user_id"]));s="approved"
 else:s="rejected"
 c.execute("UPDATE deposits SET status=? WHERE id=?",(s,i));c.commit();c.close();return jsonify(ok=True)

@app.post("/api/admin/price")
def setprice():
 if not admin():return jsonify(ok=False),403
 d=request.json or {};pid=int(d.get("product_id",0));p=float(d.get("price",0));c=db();c.execute("INSERT INTO price_overrides VALUES(?,?) ON CONFLICT(product_id) DO UPDATE SET price=excluded.price",(pid,p));c.commit();c.close();return jsonify(ok=True)

if __name__=="__main__":
 app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
