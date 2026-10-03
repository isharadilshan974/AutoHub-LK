import os
import html
import urllib.parse
from datetime import datetime
from typing import Optional

import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="AutoHub LK", page_icon="🚗", layout="wide", initial_sidebar_state="expanded")

# -----------------------------
# Configuration
# -----------------------------
APP_NAME = "AutoHub LK"
BUCKET = "vehicle-images"
CATEGORIES = ["Car", "SUV", "Van", "Motorbike", "Three Wheeler", "Lorry", "Bus", "Other"]
CONDITIONS = ["Brand New", "Used", "Reconditioned"]
FUEL_TYPES = ["Petrol", "Diesel", "Hybrid", "Electric", "Other"]


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return os.getenv(name, default)


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")


def get_client() -> Optional[Client]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as exc:
        st.error(f"Supabase connection error: {exc}")
        return None


supabase = get_client()

# Restore Supabase Auth on every Streamlit rerun.
if supabase is not None:
    try:
        access_token = st.session_state.get("access_token")
        refresh_token = st.session_state.get("refresh_token")
        if access_token and refresh_token:
            supabase.auth.set_session(access_token, refresh_token)
    except Exception:
        pass

# -----------------------------
# Session helpers
# -----------------------------
for key, default in {
    "user": None,
    "profile": None,
    "access_token": None,
    "refresh_token": None,
    "page": "Home",
    "search": "",
    "category": "All",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def current_user():
    return st.session_state.get("user")


def current_profile():
    return st.session_state.get("profile") or {}


def is_logged_in() -> bool:
    return current_user() is not None


def is_admin() -> bool:
    return current_profile().get("role") == "admin"


def require_supabase() -> bool:
    if supabase is None:
        st.warning("Supabase is not connected yet. Add SUPABASE_URL and SUPABASE_KEY in Streamlit Secrets.")
        return False
    return True


def money(value) -> str:
    try:
        return f"Rs. {float(value):,.0f}"
    except Exception:
        return "Rs. 0"


def safe(value) -> str:
    return html.escape(str(value or ""))


def set_page(name: str):
    st.session_state.page = name
    st.rerun()


def load_profile(user_id: str):
    if supabase is None:
        return None
    try:
        result = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return result.data
    except Exception:
        return None


def refresh_auth_state():
    if supabase is None:
        return
    try:
        session = supabase.auth.get_session()
        if session and getattr(session, "user", None):
            user = session.user
            st.session_state.user = user
            st.session_state.profile = load_profile(user.id) or {}
            st.session_state.access_token = getattr(session, "access_token", None)
            st.session_state.refresh_token = getattr(session, "refresh_token", None)
    except Exception:
        pass


refresh_auth_state()

# -----------------------------
# Data functions
# -----------------------------
def list_vehicles(search="", category="All", min_price=0, max_price=10**12, condition="All", location="All", limit=100):
    if supabase is None:
        return []
    try:
        q = supabase.table("vehicles").select("*, profiles(full_name, phone, city)").eq("status", "approved")
        if search.strip():
            term = search.strip()
            # PostgREST OR search across common fields.
            q = q.or_(f"make.ilike.%{term}%,model.ilike.%{term}%,title.ilike.%{term}%,location.ilike.%{term}%")
        if category != "All":
            q = q.eq("category", category)
        if condition != "All":
            q = q.eq("condition", condition)
        if location != "All":
            q = q.eq("location", location)
        q = q.gte("price", min_price).lte("price", max_price).order("created_at", desc=True).limit(limit)
        return q.execute().data or []
    except Exception as exc:
        st.error(f"Could not load vehicles: {exc}")
        return []


def get_vehicle(vehicle_id: str):
    if supabase is None:
        return None
    try:
        return supabase.table("vehicles").select("*, profiles(full_name, phone, email, city)").eq("id", vehicle_id).single().execute().data
    except Exception:
        return None


def upload_images(files, user_id: str):
    urls = []
    if not files:
        return urls
    if supabase is None:
        return urls
    for idx, file in enumerate(files[:8]):
        ext = os.path.splitext(file.name)[1].lower() or ".jpg"
        path = f"{user_id}/{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{idx}{ext}"
        try:
            supabase.storage.from_(BUCKET).upload(path, file.getvalue(), {"content-type": file.type or "image/jpeg", "upsert": "true"})
            urls.append(supabase.storage.from_(BUCKET).get_public_url(path))
        except Exception as exc:
            st.warning(f"Image upload failed for {file.name}: {exc}")
    return urls


def add_view(vehicle_id: str):
    if supabase is None:
        return
    try:
        v = supabase.table("vehicles").select("views").eq("id", vehicle_id).single().execute().data
        supabase.table("vehicles").update({"views": int(v.get("views", 0)) + 1}).eq("id", vehicle_id).execute()
    except Exception:
        pass


def favourite_ids():
    if not is_logged_in() or supabase is None:
        return set()
    try:
        rows = supabase.table("favourites").select("vehicle_id").eq("user_id", current_user().id).execute().data or []
        return {r["vehicle_id"] for r in rows}
    except Exception:
        return set()


def toggle_favourite(vehicle_id: str):
    if not is_logged_in():
        st.info("Please login to save favourites.")
        return
    try:
        existing = supabase.table("favourites").select("id").eq("user_id", current_user().id).eq("vehicle_id", vehicle_id).execute().data or []
        if existing:
            supabase.table("favourites").delete().eq("id", existing[0]["id"]).execute()
        else:
            supabase.table("favourites").insert({"user_id": current_user().id, "vehicle_id": vehicle_id}).execute()
        st.rerun()
    except Exception as exc:
        st.error(f"Favourite update failed: {exc}")


def create_enquiry(vehicle_id: str, message: str):
    if not is_logged_in():
        st.error("Please login first.")
        return False
    try:
        supabase.table("enquiries").insert({"vehicle_id": vehicle_id, "buyer_id": current_user().id, "message": message}).execute()
        return True
    except Exception as exc:
        st.error(f"Could not send enquiry: {exc}")
        return False


def whatsapp_url(phone: str, message: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if digits.startswith("0"):
        digits = "94" + digits[1:]
    return "https://wa.me/" + digits + "?text=" + urllib.parse.quote(message)


def facebook_share_url(url: str) -> str:
    return "https://www.facebook.com/sharer/sharer.php?u=" + urllib.parse.quote(url, safe="")

# -----------------------------
# CSS
# -----------------------------
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; max-width: 1250px;}
.hero {padding: 38px; border-radius: 24px; background: linear-gradient(135deg,#08152f,#1557d6); color: white; margin-bottom: 25px;}
.hero h1 {font-size: 3rem; margin-bottom: 5px;}
.badge {display:inline-block; padding:5px 10px; border-radius:999px; background:#e8f1ff; color:#1557d6; font-size:.82rem; margin-right:5px;}
.card {border:1px solid #e6e9ef; border-radius:18px; padding:14px; background:white; margin-bottom:12px; box-shadow:0 2px 10px rgba(0,0,0,.04);}
.price {font-size:1.25rem; font-weight:800;}
.small {color:#6b7280; font-size:.9rem;}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown("# 🚗 AutoHub LK")
    st.caption("Sri Lanka Vehicle Marketplace — Business Edition")
    st.divider()
    nav = ["Home", "Buy Vehicles", "Sell Vehicle", "Favourites", "Messages", "Finance Calculator"]
    if is_admin():
        nav += ["Admin Dashboard"]
    if is_logged_in():
        nav += ["My Profile", "About"]
    else:
        nav += ["Login", "About"]
    selected = st.radio("Navigation", nav, index=nav.index(st.session_state.page) if st.session_state.page in nav else 0)
    if selected != st.session_state.page:
        st.session_state.page = selected
        st.rerun()
    st.divider()
    if is_logged_in():
        st.success(f"Signed in as {current_profile().get('full_name') or current_user().email}")
        if st.button("Logout", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            st.session_state.user = None
            st.session_state.profile = None
            st.session_state.access_token = None
            st.session_state.refresh_token = None
            set_page("Home")
    else:
        if st.button("🔐 Login / Register", use_container_width=True):
            set_page("Login")

# -----------------------------
# Setup screen
# -----------------------------
if supabase is None:
    st.markdown("# 🚗 AutoHub LK — Business Edition")
    st.warning("The app is deployed, but Supabase is not connected yet.")
    st.markdown("""
### One-time setup
1. Create a Supabase project.
2. Run the supplied `supabase_schema.sql` in **SQL Editor**.
3. Create a Streamlit secret with `SUPABASE_URL` and `SUPABASE_KEY`.
4. Reboot the app.

Use the **publishable/anon key**, not the service-role key, in Streamlit. Row Level Security policies in the schema control access.
""")
    st.code('SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"\nSUPABASE_KEY = "YOUR-PUBLISHABLE-OR-ANON-KEY"', language="toml")
    st.stop()

# -----------------------------
# Home
# -----------------------------
if st.session_state.page == "Home":
    st.markdown('<div class="hero"><h1>🚗 AutoHub LK</h1><p style="font-size:1.2rem">Buy, sell and discover vehicles across Sri Lanka.</p></div>', unsafe_allow_html=True)
    vehicles = list_vehicles(limit=6)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Active listings", len(list_vehicles(limit=1000)))
    c2.metric("Verified/active sellers", len({v.get('seller_id') for v in vehicles if v.get('seller_id')}))
    c3.metric("Recent listings", len(vehicles))
    c4.metric("Total views", sum(int(v.get('views') or 0) for v in vehicles))
    st.markdown("## 🔎 Find your vehicle")
    with st.form("home_search"):
        a,b,c = st.columns([2,1,1])
        search = a.text_input("Make, model or keyword")
        cat = b.selectbox("Category", ["All"] + CATEGORIES)
        condition = c.selectbox("Condition", ["All"] + CONDITIONS)
        if st.form_submit_button("Search vehicles", use_container_width=True):
            st.session_state.search = search
            st.session_state.category = cat
            st.session_state.page = "Buy Vehicles"
            st.session_state.home_condition = condition
            st.rerun()
    st.markdown("## ⭐ Latest vehicles")
    cols = st.columns(3)
    for i, v in enumerate(vehicles[:6]):
        with cols[i % 3]:
            img = (v.get("images") or [None])[0]
            if img:
                st.image(img, use_container_width=True)
            st.markdown(f"**{safe(v.get('title'))}**")
            st.markdown(f"<div class='price'>{money(v.get('price'))}</div>", unsafe_allow_html=True)
            st.caption(f"{v.get('year') or '-'} • {v.get('mileage') or 0:,} km • {v.get('location') or '-'}")
            if st.button("View details", key=f"home_{v['id']}", use_container_width=True):
                st.session_state.vehicle_id = v["id"]
                set_page("Vehicle Details")

# -----------------------------
# Buy Vehicles
# -----------------------------
elif st.session_state.page == "Buy Vehicles":
    st.title("🚗 Buy Vehicles")
    with st.expander("🔍 Search & filters", expanded=True):
        a,b,c,d = st.columns(4)
        search = a.text_input("Search", value=st.session_state.get("search", ""))
        cat = b.selectbox("Category", ["All"] + CATEGORIES, index=(["All"] + CATEGORIES).index(st.session_state.get("category", "All")) if st.session_state.get("category", "All") in ["All"]+CATEGORIES else 0)
        condition = c.selectbox("Condition", ["All"] + CONDITIONS)
        location = d.selectbox("Location", ["All", "Colombo", "Panadura", "Moratuwa", "Kalutara", "Gampaha", "Kandy", "Galle", "Kurunegala", "Jaffna", "Other"])
        minp,maxp = st.slider("Price range (Rs.)", 0, 100_000_000, (0, 100_000_000), step=100_000)
    vehicles = list_vehicles(search, cat, minp, maxp, condition, location)
    favs = favourite_ids()
    st.write(f"**{len(vehicles)} vehicles found**")
    if not vehicles:
        st.info("No approved vehicles match these filters yet.")
    cols = st.columns(3)
    for i,v in enumerate(vehicles):
        with cols[i%3]:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            img = (v.get("images") or [None])[0]
            if img: st.image(img, use_container_width=True)
            st.markdown(f"### {safe(v.get('title'))}")
            st.markdown(f"<div class='price'>{money(v.get('price'))}</div>", unsafe_allow_html=True)
            st.caption(f"{v.get('year') or '-'} • {v.get('mileage') or 0:,} km • {v.get('location') or '-'}")
            st.markdown(f"<span class='badge'>{safe(v.get('category'))}</span> <span class='badge'>{safe(v.get('condition'))}</span>", unsafe_allow_html=True)
            a,b = st.columns(2)
            with a:
                if st.button("View", key=f"view_{v['id']}", use_container_width=True):
                    st.session_state.vehicle_id = v["id"]
                    add_view(v["id"])
                    set_page("Vehicle Details")
            with b:
                if st.button("❤️" if v["id"] in favs else "♡", key=f"fav_{v['id']}", use_container_width=True):
                    toggle_favourite(v["id"])
            st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# Vehicle details
# -----------------------------
elif st.session_state.page == "Vehicle Details":
    vehicle_id = st.session_state.get("vehicle_id")
    v = get_vehicle(vehicle_id) if vehicle_id else None
    if not v:
        st.error("Vehicle not found.")
        st.stop()
    st.title(v.get("title") or "Vehicle")
    imgs = v.get("images") or []
    if imgs:
        st.image(imgs[0], use_container_width=True)
        if len(imgs) > 1:
            cols = st.columns(min(4, len(imgs)-1))
            for i,img in enumerate(imgs[1:5]):
                cols[i].image(img, use_container_width=True)
    a,b = st.columns([2,1])
    with a:
        st.markdown(f"## {money(v.get('price'))}")
        st.write(v.get("description") or "No description provided.")
        data = {
            "Category": v.get("category"), "Make": v.get("make"), "Model": v.get("model"),
            "Year": v.get("year"), "Mileage": f"{v.get('mileage') or 0:,} km", "Fuel": v.get("fuel_type"),
            "Condition": v.get("condition"), "Transmission": v.get("transmission"), "Location": v.get("location")
        }
        st.table(data)
    with b:
        profile = v.get("profiles") or {}
        st.markdown("### 👤 Seller")
        st.write(profile.get("full_name") or "Seller")
        st.caption(profile.get("city") or v.get("location") or "Sri Lanka")
        phone = profile.get("phone") or v.get("seller_phone")
        if phone:
            msg = f"Hi, I'm interested in your {v.get('title')} listed on AutoHub LK. Is it still available?"
            st.link_button("💬 WhatsApp Seller", whatsapp_url(phone,msg), use_container_width=True)
            st.link_button("📞 Call Seller", f"tel:{phone}", use_container_width=True)
        st.link_button("📣 Share on Facebook", facebook_share_url(f"https://autohub-lk.streamlit.app/?vehicle={v.get('id')}"), use_container_width=True)
        if st.button("❤️ Save to favourites", use_container_width=True): toggle_favourite(v["id"])
    st.divider()
    st.subheader("💬 Contact seller")
    if is_logged_in():
        message = st.text_area("Your message", placeholder="Is the vehicle available? Can I arrange a viewing?")
        if st.button("Send enquiry", type="primary"):
            if message.strip() and create_enquiry(v["id"], message.strip()):
                st.success("Enquiry sent successfully.")
    else:
        st.info("Login to send an enquiry. WhatsApp and call links can still be used if provided.")

# -----------------------------
# Sell Vehicle
# -----------------------------
elif st.session_state.page == "Sell Vehicle":
    st.title("➕ Sell Your Vehicle")
    if not is_logged_in():
        st.info("Please login or register as a seller to post a vehicle.")
        if st.button("Login / Register", type="primary"): set_page("Login")
    else:
        with st.form("sell_form"):
            a,b = st.columns(2)
            title = a.text_input("Listing title *", placeholder="Toyota Raize 2022 — Excellent Condition")
            category = b.selectbox("Category *", CATEGORIES)
            c,d,e = st.columns(3)
            make = c.text_input("Make *")
            model = d.text_input("Model *")
            year = e.number_input("Year", 1950, datetime.now().year+1, 2020)
            f,g,h = st.columns(3)
            price = f.number_input("Price (Rs.) *", 0, 500_000_000, 5_000_000, step=50_000)
            mileage = g.number_input("Mileage (km)", 0, 2_000_000, 50_000, step=1_000)
            condition = h.selectbox("Condition", CONDITIONS)
            i,j,k = st.columns(3)
            fuel = i.selectbox("Fuel", FUEL_TYPES)
            transmission = j.selectbox("Transmission", ["Automatic", "Manual", "Other"])
            location = k.selectbox("Location", ["Colombo", "Panadura", "Moratuwa", "Kalutara", "Gampaha", "Kandy", "Galle", "Kurunegala", "Jaffna", "Other"])
            description = st.text_area("Description", height=140)
            images = st.file_uploader("Vehicle photos (up to 8)", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
            submitted = st.form_submit_button("Submit listing for approval", type="primary", use_container_width=True)
        if submitted:
            if not title.strip() or not make.strip() or not model.strip() or price <= 0:
                st.error("Please fill the required fields.")
            else:
                with st.spinner("Uploading and creating listing..."):
                    image_urls = upload_images(images, current_user().id)
                    payload = {
                        "seller_id": current_user().id, "title": title.strip(), "category": category,
                        "make": make.strip(), "model": model.strip(), "year": int(year), "price": float(price),
                        "mileage": int(mileage), "condition": condition, "fuel_type": fuel,
                        "transmission": transmission, "location": location, "description": description.strip(),
                        "images": image_urls, "status": "pending", "views": 0
                    }
                    try:
                        supabase.table("vehicles").insert(payload).execute()
                        st.success("Vehicle submitted. Admin approval is required before it appears publicly.")
                    except Exception as exc:
                        st.error(f"Could not create listing: {exc}")

# -----------------------------
# Favourites
# -----------------------------
elif st.session_state.page == "Favourites":
    st.title("❤️ My Favourites")
    if not is_logged_in():
        st.info("Login to see your favourites.")
    else:
        ids = favourite_ids()
        vehicles = []
        for vid in ids:
            v = get_vehicle(vid)
            if v: vehicles.append(v)
        if not vehicles: st.info("No favourites yet.")
        for v in vehicles:
            with st.container(border=True):
                a,b,c = st.columns([1,2,1])
                img=(v.get("images") or [None])[0]
                if img: a.image(img, use_container_width=True)
                b.markdown(f"### {v.get('title')}")
                b.write(money(v.get("price")))
                if c.button("View", key=f"favview_{v['id']}"): st.session_state.vehicle_id=v["id"]; set_page("Vehicle Details")

# -----------------------------
# Messages / enquiries
# -----------------------------
elif st.session_state.page == "Messages":
    st.title("💬 Messages & Enquiries")
    if not is_logged_in():
        st.info("Login to view messages.")
    else:
        if is_admin():
            rows = supabase.table("enquiries").select("*, vehicles(title), profiles!enquiries_buyer_id_fkey(full_name,email,phone)").order("created_at", desc=True).execute().data or []
        else:
            rows = supabase.table("enquiries").select("*, vehicles(title)").eq("buyer_id", current_user().id).order("created_at", desc=True).execute().data or []
        if not rows: st.info("No enquiries yet.")
        for r in rows:
            with st.container(border=True):
                st.markdown(f"**{(r.get('vehicles') or {}).get('title','Vehicle')}**")
                st.write(r.get("message"))
                st.caption(f"Status: {r.get('status','new')} • {r.get('created_at','')}")

# -----------------------------
# Finance calculator
# -----------------------------
elif st.session_state.page == "Finance Calculator":
    st.title("💰 Vehicle Finance Calculator")
    st.caption("Planning estimate only — actual approval, rates and insurance depend on the finance provider.")
    a,b,c = st.columns(3)
    vehicle_price = a.number_input("Vehicle price (Rs.)", 0, 500_000_000, 5_000_000, step=50_000)
    down = b.number_input("Down payment (Rs.)", 0, 500_000_000, int(vehicle_price*0.40), step=50_000)
    annual = c.number_input("Annual interest rate (%)", 0.0, 50.0, 24.0, step=0.5)
    months = st.selectbox("Period", [12,24,36,48,60,72,84], index=4)
    financed=max(0,vehicle_price-down)
    r=annual/100/12
    monthly=(financed*r*(1+r)**months/((1+r)**months-1)) if r and financed else (financed/months if months else 0)
    x,y,z=st.columns(3)
    x.metric("Financed amount", money(financed)); y.metric("Monthly estimate", money(monthly)); z.metric("Total instalments", money(monthly*months))

# -----------------------------
# Login / Register
# -----------------------------
elif st.session_state.page == "Login":
    st.title("🔐 AutoHub LK Account")
    login_tab, register_tab = st.tabs(["Login", "Create account"])
    with login_tab:
        email=st.text_input("Email", key="login_email")
        password=st.text_input("Password", type="password", key="login_password")
        if st.button("Login", type="primary", use_container_width=True):
            try:
                result=supabase.auth.sign_in_with_password({"email":email.strip(),"password":password})
                st.session_state.user = result.user
                st.session_state.profile = load_profile(result.user.id) or {}
                if getattr(result, "session", None):
                    st.session_state.access_token = result.session.access_token
                    st.session_state.refresh_token = result.session.refresh_token
                    try:
                        supabase.auth.set_session(
                            result.session.access_token,
                            result.session.refresh_token,
                        )
                    except Exception:
                        pass
                set_page("Home")
            except Exception as exc: st.error(f"Login failed: {exc}")
    with register_tab:
        name=st.text_input("Full name", key="reg_name")
        email=st.text_input("Email", key="reg_email")
        phone=st.text_input("Phone", key="reg_phone")
        city=st.text_input("City", key="reg_city")
        role=st.selectbox("Account type", ["buyer","seller","dealer"])
        password=st.text_input("Password", type="password", key="reg_password")
        if st.button("Create account", type="primary", use_container_width=True):
            try:
                result=supabase.auth.sign_up({"email":email.strip(),"password":password,"options":{"data":{"full_name":name.strip(),"phone":phone.strip(),"city":city.strip(),"role":role}}})
                if getattr(result, "user", None):
                    if getattr(result, "session", None):
                        st.session_state.user = result.user
                        st.session_state.profile = load_profile(result.user.id) or {}
                        st.session_state.access_token = result.session.access_token
                        st.session_state.refresh_token = result.session.refresh_token
                        try:
                            supabase.auth.set_session(
                                result.session.access_token,
                                result.session.refresh_token,
                            )
                        except Exception:
                            pass
                    st.success("Account created. If email confirmation is enabled in Supabase, confirm your email before logging in.")
                else:
                    st.success("Registration submitted.")
            except Exception as exc: st.error(f"Registration failed: {exc}")

# -----------------------------
# Admin
# -----------------------------
elif st.session_state.page == "Admin Dashboard":
    if not is_admin():
        st.error("Admin access required.")
        st.stop()
    st.title("🛡️ Admin Dashboard")
    pending=supabase.table("vehicles").select("*, profiles(full_name,email)").eq("status","pending").order("created_at",desc=True).execute().data or []
    approved=supabase.table("vehicles").select("id").eq("status","approved").execute().data or []
    users=supabase.table("profiles").select("id").execute().data or []
    a,b,c=st.columns(3); a.metric("Pending listings",len(pending)); b.metric("Approved listings",len(approved)); c.metric("Users",len(users))
    st.subheader("Pending listings")
    for v in pending:
        with st.container(border=True):
            st.markdown(f"### {v.get('title')} — {money(v.get('price'))}")
            st.write(f"Seller: {(v.get('profiles') or {}).get('full_name')} • {v.get('location')}")
            img=(v.get('images') or [None])[0]
            if img: st.image(img,width=280)
            x,y,z=st.columns(3)
            if x.button("✅ Approve",key=f"approve_{v['id']}"):
                supabase.table("vehicles").update({"status":"approved"}).eq("id",v["id"]).execute(); st.rerun()
            if y.button("❌ Reject",key=f"reject_{v['id']}"):
                supabase.table("vehicles").update({"status":"rejected"}).eq("id",v["id"]).execute(); st.rerun()
            if z.button("🗑️ Delete",key=f"delete_{v['id']}"):
                supabase.table("vehicles").delete().eq("id",v["id"]).execute(); st.rerun()

# -----------------------------
# Profile
# -----------------------------
elif st.session_state.page == "My Profile":
    st.title("👤 My Profile")
    if not is_logged_in():
        st.info("Login to manage your profile.")
    else:
        p=current_profile()
        with st.form("profile"):
            name=st.text_input("Full name",value=p.get("full_name", ""))
            phone=st.text_input("Phone",value=p.get("phone", ""))
            city=st.text_input("City",value=p.get("city", ""))
            bio=st.text_area("Bio",value=p.get("bio", ""))
            if st.form_submit_button("Save profile",type="primary"):
                try:
                    updated=supabase.table("profiles").update({"full_name":name.strip(),"phone":phone.strip(),"city":city.strip(),"bio":bio.strip()}).eq("id",current_user().id).execute().data[0]
                    st.session_state.profile=updated
                    st.success("Profile updated.")
                except Exception as exc: st.error(f"Profile update failed: {exc}")

# -----------------------------
# About
# -----------------------------
elif st.session_state.page == "About":
    st.title("ℹ️ About AutoHub LK")
    st.write("AutoHub LK is a Sri Lankan vehicle marketplace project designed to connect buyers and sellers, support vehicle discovery, enquiries, finance estimates and seller tools.")
    st.markdown("### Business Edition architecture")
    st.markdown("- **Frontend:** Streamlit + Python\n- **Authentication:** Supabase Auth\n- **Database:** Supabase PostgreSQL\n- **Images:** Supabase Storage\n- **Deployment:** Streamlit Community Cloud\n- **Security:** Row Level Security (RLS) + secrets management\n- **Social:** Share links and WhatsApp contact workflows\n- **Roadmap:** Realtime chat, notifications, analytics, dealer tools and compliant official API integrations")

