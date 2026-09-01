import os
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd
import requests
import streamlit as st
from sqlalchemy import create_engine, text

from dotenv import load_dotenv
load_dotenv(".env")


def live_status(created_at):
    created_at = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
    seconds = (datetime.now() - created_at).total_seconds()
    return "Delivered" if seconds > 180 else "Out for Delivery" if seconds > 120 else "Preparing" if seconds > 60 else "Placed"


def bill(order, user):
    items = "\n".join(f"- {item}" for item in order['items'].split(", "))
    return "\n".join([
        "TapNGo Bill",
        f"Customer: {user['name']}",
        f"Hotel: {order['restaurant']}",
        f"Items:\n{items}",
        f"Total: Rs {int(order['total'])}",
        f"Status: {order['status']}",
        f"Time: {order['created_at']}",
    ])


@st.cache_data(ttl=3600)
def geocode(address):
    if not os.getenv("RAPIDAPI_KEY"):
        return 12.9716, 77.5946
    resp = requests.get(
        f"https://{os.getenv('RAPIDAPI_GEO_HOST', 'forward-reverse-geocoding.p.rapidapi.com')}/v1/search",
        headers={"X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"), "X-RapidAPI-Host": os.getenv("RAPIDAPI_GEO_HOST", "forward-reverse-geocoding.p.rapidapi.com")},
        params={"q": address, "accept-language": "en", "polygon_threshold": "0.0"},
        timeout=10,
    )
    first = resp.json()[0]
    return float(first["lat"]), float(first["lon"])


@st.cache_data(ttl=3600)
def recipes():
    return requests.get("https://dummyjson.com/recipes?limit=0&select=name,cuisine,rating,image,caloriesPerServing", timeout=10).json()["recipes"]


def cuisine_for(name):
    text_name = name.lower()
    for word, cuisine in (("dosa", "Indian"), ("udupi", "Indian"), ("kachori", "Indian"), ("pizza", "Italian"), ("pasta", "Italian"), ("biryani", "Pakistani"), ("kebab", "Pakistani"), ("karahi", "Pakistani"), ("mughlai", "Pakistani")):
        if word in text_name:
            return cuisine
    return ("Indian", "Italian", "Pakistani")[sum(map(ord, text_name)) % 3]


@st.cache_data(ttl=1800)
def nearby_hotels(address):
    places = requests.get("https://nominatim.openstreetmap.org/search", params={"q": f"restaurants in {address}", "format": "jsonv2", "limit": 6}, headers={"User-Agent": "tapngo-app"}, timeout=20).json()
    data = {}
    for place in places:
        name = place.get("name") or place["display_name"].split(",")[0]
        cuisine = cuisine_for(f"{name} {place['display_name']}")
        menu = [r for r in recipes() if r["cuisine"] == cuisine or cuisine == "Indian" and any(k in r["name"].lower() for k in ("dosa", "lassi"))][:4]
        if menu:
            data[name] = {"cuisine": cuisine, "lat": float(place["lat"]), "lon": float(place["lon"]), "menu": menu, "rating": round(sum(i["rating"] for i in menu) / len(menu), 1)}
    return data


engine = create_engine(f"mysql+pymysql://{os.getenv('DB_USER')}:{quote_plus(os.getenv('DB_PASSWORD', ''))}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME')}", pool_pre_ping=True)
with engine.begin() as conn:
    conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(120), email VARCHAR(160) UNIQUE, password VARCHAR(120), address VARCHAR(255), lat DOUBLE, lng DOUBLE)"))
    conn.execute(text("CREATE TABLE IF NOT EXISTS orders (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, restaurant VARCHAR(120), items TEXT, total DOUBLE, status VARCHAR(40) DEFAULT 'Placed', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)"))

st.set_page_config(page_title="TapNGo", page_icon="🛵", layout="centered")
st.session_state.setdefault("user_id", None)
st.title("🛵 TapNGo")
st.caption(f"Database: {os.getenv('DB_HOST')} ({os.getenv('DB_NAME')})")

if not st.session_state.user_id:
    a, b = st.tabs(["Login", "Sign up"])
    with a:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                with engine.connect() as conn:
                    user = conn.execute(text("SELECT * FROM users WHERE email=:email AND password=:password"), {"email": email, "password": password}).mappings().first()
                if user:
                    st.session_state.user_id = user["id"]
                    st.rerun()
                st.error("Invalid login")
    with b:
        with st.form("signup"):
            name = st.text_input("Name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            if st.form_submit_button("Create account"):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO users(name,email,password) VALUES(:name,:email,:password)"), {"name": name, "email": email, "password": password})
                    st.success("Account created")
                except Exception:
                    st.error("Email already exists")
else:
    with engine.connect() as conn:
        user = conn.execute(text("SELECT * FROM users WHERE id=:id"), {"id": st.session_state.user_id}).mappings().first()
        order = conn.execute(text("SELECT * FROM orders WHERE user_id=:id ORDER BY id DESC LIMIT 1"), {"id": st.session_state.user_id}).mappings().first()
    hotels = nearby_hotels(user["address"]) if user["address"] else {}
    st.write(f"Hello, {user['name']}")
    address = st.text_input("Delivery address", value=user["address"] or "")
    if st.button("Save location") and address:
        lat, lng = geocode(address)
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET address=:address, lat=:lat, lng=:lng WHERE id=:id"), {"address": address, "lat": lat, "lng": lng, "id": user["id"]})
        st.rerun()
    if user["lat"] and user["lng"]:
        pins = [{"lat": user["lat"], "lon": user["lng"]}] + [{"lat": h["lat"], "lon": h["lon"]} for h in hotels.values()]
        st.map(pd.DataFrame(pins), zoom=12)
    if hotels:
        st.subheader("Hotels")
        for name, hotel in hotels.items():
            st.write(f"{name} | {hotel['cuisine']} | {hotel['rating']} stars")
        restaurant = st.selectbox("Choose hotel", list(hotels))
        st.subheader("Menu")
        items, total = [], 0
        for dish in hotels[restaurant]["menu"]:
            price = max(80, int(dish.get("caloriesPerServing", 200) / 2))
            qty = st.number_input(f"{dish['name']} - Rs {price}", 0, 10, 0, 1)
            if qty:
                items.append(f"{qty} x {dish['name']}")
                total += qty * price
        if st.button("Place order") and items:
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO orders(user_id,restaurant,items,total,status) VALUES(:user_id,:restaurant,:items,:total,'Placed')"), {"user_id": user["id"], "restaurant": restaurant, "items": ", ".join(items), "total": total})
            st.rerun()
    elif user["address"]:
        st.info("No live hotels found for this location right now.")
    if order:
        status = live_status(order["created_at"])
        if status != order["status"]:
            with engine.begin() as conn:
                conn.execute(text("UPDATE orders SET status=:status WHERE id=:id"), {"status": status, "id": order["id"]})
            # order["status"] = status
        st.subheader("Live order status")
        st.progress({"Placed": .25, "Preparing": .5, "Out for Delivery": .75, "Delivered": 1}[status], text=status)
        st.write(order["restaurant"])
        st.write(order["items"])
        st.write(f"Total: Rs {int(order['total'])}")
        st.subheader("Bill")
        st.code(bill(order, user))
        st.download_button("Download bill", bill(order, user), file_name="tapngo_bill.pdf")
        if st.button("Refresh status"):
            st.rerun()
    if st.button("Logout"):
        st.session_state.user_id = None
        st.rerun()
