
import streamlit as st
import sqlite3
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "data" / "autohub.db"
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="AutoHub LK",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

CATEGORIES = ["Car", "SUV", "Van", "Motorbike", "Three Wheeler", "Lorry", "Bus", "Other"]
CONDITIONS = ["Brand New", "Used", "Reconditioned"]
STATUSES = ["Pending", "Approved", "Rejected", "Sold"]

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def execute(sql, params=()):
    con = db()
    cur = con.execute(sql, params)
    con.commit()
    last_id = cur.lastrowid
    con.close()
    return last_id

def fetchall(sql, params=()):
    con = db()
    rows = con.execute(sql, params).fetchall()
    con.close()
    return rows

def fetchone(sql, params=()):
    con = db()
    row = con.execute(sql, params).fetchone()
    con.close()
    return row

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'buyer',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS vehicles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        make TEXT,
        model TEXT,
        year INTEGER,
        price REAL NOT NULL,
        mileage REAL DEFAULT 0,
        condition TEXT,
        location TEXT,
        description TEXT,
        phone TEXT,
        image_path TEXT,
        status TEXT NOT NULL DEFAULT 'Pending',
        views INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (seller_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS favourites (
        user_id INTEGER NOT NULL,
        vehicle_id INTEGER NOT NULL,
        PRIMARY KEY (user_id, vehicle_id)
    );

    CREATE TABLE IF NOT EXISTS enquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL,
        buyer_id INTEGER,
        buyer_name TEXT,
        buyer_phone TEXT,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'New'
    );

    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL,
        reporter_email TEXT,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open'
    );
    """)
    admin = con.execute(
        "SELECT id FROM users WHERE email=?",
        ("admin@autohub.lk",)
    ).fetchone()
    if not admin:
        con.execute(
            """INSERT INTO users(name,email,phone,password,role,created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                "AutoHub Admin",
                "admin@autohub.lk",
                "",
                hash_password("admin1234"),
                "admin",
                now(),
            ),
        )
    con.commit()
    con.close()

def seed_demo():
    if fetchone("SELECT id FROM vehicles LIMIT 1"):
        return
    seller = execute(
        """INSERT INTO users(name,email,phone,password,role,created_at)
           VALUES(?,?,?,?,?,?)""",
        (
            "Demo Seller",
            "seller@autohub.lk",
            "0771234567",
            hash_password("seller1234"),
            "seller",
            now(),
        ),
    )
    demo = [
        ("Toyota Raize Hybrid", "Car", "Toyota", "Raize", 2023, 14500000, 25000,
         "Used", "Colombo", "Hybrid SUV in good condition.", "0771234567"),
        ("Honda Vezel", "SUV", "Honda", "Vezel", 2020, 13250000, 42000,
         "Used", "Panadura", "Well maintained vehicle.", "0771234567"),
        ("TVS Raider 125", "Motorbike", "TVS", "Raider", 2024, 485000, 7000,
         "Used", "Kalutara", "Economical commuter bike.", "0771234567"),
    ]
    for item in demo:
        execute(
            """INSERT INTO vehicles
            (seller_id,title,category,make,model,year,price,mileage,condition,
             location,description,phone,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (seller, *item, "Approved", now()),
        )

def current_user():
    uid = st.session_state.get("user_id")
    if not uid:
        return None
    return fetchone("SELECT * FROM users WHERE id=?", (uid,))

def money(value):
    return f"Rs. {value:,.0f}"

def save_image(uploaded, vehicle_id):
    if not uploaded:
        return ""
    ext = Path(uploaded.name).suffix.lower() or ".jpg"
    filename = f"vehicle_{vehicle_id}_{uuid.uuid4().hex[:10]}{ext}"
    destination = UPLOAD_DIR / filename
    destination.write_bytes(uploaded.getbuffer())
    return str(Path("uploads") / filename)

def whatsapp_url(phone, message):
    digits = "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")
    if digits.startswith("0"):
        digits = "94" + digits[1:]
    if not digits:
        return "https://wa.me/"
    return f"https://wa.me/{digits}?text={quote(message)}"

def vehicle_card(v, user):
    left, right = st.columns([1, 2])
    with left:
        image = v["image_path"]
        image_file = APP_DIR / image if image else None
        if image_file and image_file.exists():
            st.image(str(image_file), use_container_width=True)
        else:
            st.markdown("### 🚗")
    with right:
        st.subheader(v["title"])
        st.write(f"**{money(v['price'])}**")
        st.caption(
            f"{v['category']} · {v['condition'] or 'Used'} · "
            f"{v['year'] or 'N/A'} · {v['mileage']:,.0f} km · "
            f"{v['location'] or 'Sri Lanka'}"
        )
        description = v["description"] or ""
        st.write(description[:220] + ("..." if len(description) > 220 else ""))

        b1, b2, b3 = st.columns(3)

        if b1.button("View details", key=f"view_{v['id']}"):
            execute("UPDATE vehicles SET views=views+1 WHERE id=?", (v["id"],))
            st.session_state["selected_vehicle"] = v["id"]
            st.rerun()

        favourite = False
        if user:
            favourite = bool(fetchone(
                "SELECT 1 FROM favourites WHERE user_id=? AND vehicle_id=?",
                (user["id"], v["id"])
            ))

        if b2.button("❤️" if favourite else "♡", key=f"fav_{v['id']}"):
            if not user:
                st.warning("Please login to save favourites.")
            elif favourite:
                execute(
                    "DELETE FROM favourites WHERE user_id=? AND vehicle_id=?",
                    (user["id"], v["id"])
                )
            else:
                execute(
                    "INSERT OR IGNORE INTO favourites(user_id,vehicle_id) VALUES(?,?)",
                    (user["id"], v["id"])
                )
            st.rerun()

        b3.link_button(
            "WhatsApp",
            whatsapp_url(
                v["phone"],
                f"Hi, I'm interested in your {v['title']} on AutoHub LK. Vehicle ID: {v['id']}"
            )
        )
    st.divider()

def show_vehicle_details(vehicle_id, user):
    v = fetchone("SELECT * FROM vehicles WHERE id=?", (vehicle_id,))
    if not v:
        st.error("Vehicle not found.")
        return

    st.button("← Back to listings", on_click=lambda: st.session_state.pop("selected_vehicle", None))
    st.title(v["title"])

    a, b = st.columns([1.2, 1])
    with a:
        image = v["image_path"]
        image_file = APP_DIR / image if image else None
        if image_file and image_file.exists():
            st.image(str(image_file), use_container_width=True)
        else:
            st.info("No photo uploaded.")
    with b:
        st.metric("Price", money(v["price"]))
        st.write(f"**Category:** {v['category']}")
        st.write(f"**Make:** {v['make'] or 'N/A'}")
        st.write(f"**Model:** {v['model'] or 'N/A'}")
        st.write(f"**Year:** {v['year'] or 'N/A'}")
        st.write(f"**Mileage:** {v['mileage']:,.0f} km")
        st.write(f"**Condition:** {v['condition'] or 'N/A'}")
        st.write(f"**Location:** {v['location'] or 'N/A'}")
        st.link_button(
            "Contact on WhatsApp",
            whatsapp_url(
                v["phone"],
                f"Hi, I'm interested in your {v['title']} on AutoHub LK. Vehicle ID: {v['id']}"
            )
        )

    st.subheader("Description")
    st.write(v["description"] or "No description.")

    st.subheader("Send an enquiry")
    with st.form(f"enquiry_{v['id']}"):
        name = st.text_input("Your name", value=user["name"] if user else "")
        phone = st.text_input("Your phone", value=user["phone"] if user else "")
        message = st.text_area("Message", "Is this vehicle still available?")
        send = st.form_submit_button("Send enquiry")
    if send:
        if not name or not phone or not message:
            st.error("Please complete all enquiry fields.")
        else:
            execute(
                """INSERT INTO enquiries
                   (vehicle_id,buyer_id,buyer_name,buyer_phone,message,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (
                    v["id"],
                    user["id"] if user else None,
                    name,
                    phone,
                    message,
                    now(),
                )
            )
            st.success("Enquiry sent to the AutoHub LK system.")

def login_box():
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        user = fetchone(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email.strip().lower(), hash_password(password))
        )
        if user:
            st.session_state.user_id = user["id"]
            st.success("Login successful.")
            st.rerun()
        else:
            st.error("Invalid email or password.")

def register_box():
    with st.form("register_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        password = st.text_input("Password", type="password")
        role = st.selectbox("Account type", ["buyer", "seller"])
        submitted = st.form_submit_button("Create account")
    if submitted:
        if not name or not email or not password:
            st.error("Name, email and password are required.")
            return
        try:
            uid = execute(
                """INSERT INTO users(name,email,phone,password,role,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (
                    name,
                    email.strip().lower(),
                    phone,
                    hash_password(password),
                    role,
                    now(),
                )
            )
            st.session_state.user_id = uid
            st.success("Account created.")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("That email is already registered.")

def finance_page():
    st.title("💰 Finance Calculator")
    st.caption("Estimate only. Actual approval, rates and fees depend on the finance provider.")

    price = st.number_input(
        "Vehicle price (Rs.)", min_value=10000.0,
        max_value=100000000.0, value=10000000.0, step=100000.0
    )
    down = st.number_input(
        "Down payment (Rs.)", min_value=0.0,
        max_value=price, value=min(price * 0.40, price), step=10000.0
    )
    annual = st.number_input("Annual interest rate (%)", 0.0, 60.0, 24.0, 0.5)
    months = st.selectbox("Term (months)", [12, 24, 36, 48, 60], index=2)

    principal = max(price - down, 0)
    monthly_rate = annual / 100 / 12
    if monthly_rate == 0:
        payment = principal / months
    else:
        payment = (
            principal * monthly_rate * (1 + monthly_rate) ** months
            / ((1 + monthly_rate) ** months - 1)
        )

    a, b, c = st.columns(3)
    a.metric("Finance amount", money(principal))
    b.metric("Estimated monthly payment", money(payment))
    c.metric("Estimated total", money(payment * months))

def seller_dashboard(user):
    st.title("📊 Seller Dashboard")
    vehicles = fetchall(
        "SELECT * FROM vehicles WHERE seller_id=? ORDER BY created_at DESC",
        (user["id"],)
    )
    total = len(vehicles)
    approved = sum(v["status"] == "Approved" for v in vehicles)
    views = sum(v["views"] for v in vehicles)

    a, b, c = st.columns(3)
    a.metric("My listings", total)
    b.metric("Approved", approved)
    c.metric("Views", views)

    st.subheader("My vehicles")
    for v in vehicles:
        st.write(
            f"**#{v['id']} {v['title']}** — {money(v['price'])} — "
            f"{v['status']} — {v['views']} views"
        )
        st.caption(v["description"] or "")

    enquiries = fetchall(
        """SELECT e.*, v.title FROM enquiries e
           JOIN vehicles v ON v.id=e.vehicle_id
           WHERE v.seller_id=? ORDER BY e.created_at DESC""",
        (user["id"],)
    )
    st.subheader("Enquiries")
    for e in enquiries:
        st.info(
            f"**{e['buyer_name']}** ({e['buyer_phone']}) — "
            f"{e['title']}\n\n{e['message']}"
        )
    if not enquiries:
        st.caption("No enquiries yet.")

def admin_dashboard():
    st.title("🛠️ Admin Dashboard")
    vehicles = fetchall(
        """SELECT v.*, u.name AS seller_name
           FROM vehicles v JOIN users u ON u.id=v.seller_id
           ORDER BY v.created_at DESC"""
    )
    a, b, c, d = st.columns(4)
    a.metric("All listings", len(vehicles))
    b.metric("Pending", sum(v["status"] == "Pending" for v in vehicles))
    c.metric("Approved", sum(v["status"] == "Approved" for v in vehicles))
    d.metric("Total views", sum(v["views"] for v in vehicles))

    st.subheader("Pending approvals")
    pending = [v for v in vehicles if v["status"] == "Pending"]
    for v in pending:
        x, y, z = st.columns([5, 1, 1])
        x.write(f"**#{v['id']} {v['title']}** — {money(v['price'])} — {v['seller_name']}")
        if y.button("Approve", key=f"approve_{v['id']}"):
            execute("UPDATE vehicles SET status='Approved' WHERE id=?", (v["id"],))
            st.rerun()
        if z.button("Reject", key=f"reject_{v['id']}"):
            execute("UPDATE vehicles SET status='Rejected' WHERE id=?", (v["id"],))
            st.rerun()

    st.subheader("Recent enquiries")
    enquiries = fetchall(
        """SELECT e.*, v.title FROM enquiries e
           JOIN vehicles v ON v.id=e.vehicle_id
           ORDER BY e.created_at DESC"""
    )
    for e in enquiries:
        st.write(f"**{e['title']}** — {e['buyer_name']} — {e['buyer_phone']} — {e['status']}")
        st.caption(e["message"])

def sell_page(user):
    st.title("➕ Sell Your Vehicle")
    if not user:
        st.warning("Login/register as a seller first.")
        return

    if user["role"] not in ("seller", "admin"):
        st.info("A seller account is required to publish vehicle listings.")
        return

    with st.form("vehicle_form"):
        title = st.text_input("Ad title *")
        a, b, c = st.columns(3)
        category = a.selectbox("Category", CATEGORIES)
        make = b.text_input("Make")
        model = c.text_input("Model")

        a, b, c = st.columns(3)
        year = a.number_input("Year", 1900, 2100, 2022)
        price = b.number_input("Price (Rs.)", 0.0, 1000000000.0, 1000000.0, 10000.0)
        mileage = c.number_input("Mileage (km)", 0.0, 2000000.0, 0.0, 1000.0)

        condition = st.selectbox("Condition", CONDITIONS)
        location = st.text_input("Location", "Sri Lanka")
        phone = st.text_input("Contact phone", user["phone"] or "")
        description = st.text_area("Description")
        image = st.file_uploader(
            "Main vehicle photo",
            type=["jpg", "jpeg", "png", "webp"]
        )
        submit = st.form_submit_button("Submit listing")

    if submit:
        if not title or price <= 0:
            st.error("Title and valid price are required.")
            return

        vehicle_id = execute(
            """INSERT INTO vehicles
               (seller_id,title,category,make,model,year,price,mileage,condition,
                location,description,phone,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["id"], title, category, make, model, year, price, mileage,
                condition, location, description, phone, "Pending", now()
            )
        )

        image_path = save_image(image, vehicle_id)
        if image_path:
            execute(
                "UPDATE vehicles SET image_path=? WHERE id=?",
                (image_path, vehicle_id)
            )

        st.success("Listing submitted. It will appear publicly after admin approval.")

def home_page(user):
    st.markdown(
        """
        <div style="
            padding:32px;
            border-radius:24px;
            background:linear-gradient(135deg,#0b1220,#1d4ed8);
            color:white;
            margin-bottom:24px;">
            <h1 style="margin:0;">🚗 AutoHub LK</h1>
            <p style="font-size:19px;">
                Buy, sell and discover vehicles across Sri Lanka.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a, b, c = st.columns(3)
    total = fetchone(
        "SELECT COUNT(*) AS n FROM vehicles WHERE status='Approved'"
    )["n"]
    sellers = fetchone(
        "SELECT COUNT(*) AS n FROM users WHERE role IN ('seller','dealer')"
    )["n"]
    views = fetchone(
        "SELECT COALESCE(SUM(views),0) AS n FROM vehicles"
    )["n"]
    a.metric("Active listings", total)
    b.metric("Sellers", sellers)
    c.metric("Vehicle views", views)

    st.subheader("🔎 Find a vehicle")
    q = st.text_input("Search make, model or keyword")
    category = st.selectbox("Category", ["All"] + CATEGORIES)

    sql = "SELECT * FROM vehicles WHERE status='Approved'"
    params = []
    if q:
        sql += " AND (title LIKE ? OR make LIKE ? OR model LIKE ? OR description LIKE ?)"
        params.extend([f"%{q}%"] * 4)
    if category != "All":
        sql += " AND category=?"
        params.append(category)
    sql += " ORDER BY created_at DESC LIMIT 12"

    st.subheader("🔥 Latest Vehicles")
    vehicles = fetchall(sql, params)
    if not vehicles:
        st.info("No vehicles found.")
    for v in vehicles:
        vehicle_card(v, user)

def listings_page(user):
    st.title("🔎 Buy Vehicles")
    a, b, c, d = st.columns(4)
    q = a.text_input("Keyword")
    category = b.selectbox("Category", ["All"] + CATEGORIES)
    condition = c.selectbox("Condition", ["All"] + CONDITIONS)
    sort = d.selectbox(
        "Sort",
        ["Newest", "Price: Low to High", "Price: High to Low"]
    )

    sql = "SELECT * FROM vehicles WHERE status='Approved'"
    params = []

    if q:
        sql += " AND (title LIKE ? OR make LIKE ? OR model LIKE ? OR location LIKE ?)"
        params.extend([f"%{q}%"] * 4)
    if category != "All":
        sql += " AND category=?"
        params.append(category)
    if condition != "All":
        sql += " AND condition=?"
        params.append(condition)

    if sort == "Price: Low to High":
        sql += " ORDER BY price ASC"
    elif sort == "Price: High to Low":
        sql += " ORDER BY price DESC"
    else:
        sql += " ORDER BY created_at DESC"

    vehicles = fetchall(sql, params)
    if not vehicles:
        st.info("No matching vehicles.")
    for v in vehicles:
        vehicle_card(v, user)

def favourites_page(user):
    st.title("❤️ Favourites")
    if not user:
        st.info("Login to use favourites.")
        return

    vehicles = fetchall(
        """SELECT v.* FROM vehicles v
           JOIN favourites f ON f.vehicle_id=v.id
           WHERE f.user_id=?
           ORDER BY v.created_at DESC""",
        (user["id"],)
    )
    if not vehicles:
        st.info("No favourites yet.")
    for v in vehicles:
        vehicle_card(v, user)

def about_page():
    st.title("ℹ️ About AutoHub LK")
    st.write(
        "AutoHub LK is a Sri Lankan vehicle marketplace concept designed "
        "to connect buyers, sellers and brokers."
    )
    st.subheader("Current platform")
    st.write(
        "Vehicle listings, search and filters, seller accounts, favourites, "
        "enquiries, finance estimates, admin moderation and WhatsApp sharing."
    )
    st.subheader("Future platform")
    st.write(
        "Dealer tools, advanced analytics, finance application workflows, "
        "notifications, AI assistance and official social/WhatsApp integrations."
    )

init_db()
seed_demo()

user = current_user()

st.sidebar.title("🚗 AutoHub LK")
st.sidebar.caption("Python + Streamlit Vehicle Marketplace")

if user:
    st.sidebar.success(f"Signed in: {user['name']}")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.pop("user_id", None)
        st.rerun()
else:
    st.sidebar.info("Browse listings without an account.")

menu = ["🏠 Home", "🔎 Buy Vehicles", "➕ Sell Vehicle", "❤️ Favourites",
        "💰 Finance Calculator", "🔐 Login / Register", "ℹ️ About"]
if user and user["role"] == "admin":
    menu.append("🛠️ Admin Dashboard")
elif user and user["role"] == "seller":
    menu.append("📊 Seller Dashboard")

page = st.sidebar.radio("Navigation", menu)

if "selected_vehicle" in st.session_state:
    show_vehicle_details(st.session_state["selected_vehicle"], user)
elif page == "🏠 Home":
    home_page(user)
elif page == "🔎 Buy Vehicles":
    listings_page(user)
elif page == "➕ Sell Vehicle":
    sell_page(user)
elif page == "❤️ Favourites":
    favourites_page(user)
elif page == "💰 Finance Calculator":
    finance_page()
elif page == "🔐 Login / Register":
    st.title("🔐 Account")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        login_box()
    with tab2:
        register_box()
elif page == "📊 Seller Dashboard":
    seller_dashboard(user)
elif page == "🛠️ Admin Dashboard":
    admin_dashboard()
elif page == "ℹ️ About":
    about_page()
