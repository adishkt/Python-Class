# TapNGo — Bangalore Food Delivery App

A Streamlit food delivery app backed by a Filess.io MySQL database and RapidAPI
geocoding for Bangalore delivery addresses.

## Features
- Simple profile flow with name + email only
- Save a delivery address, geocoded to lat/lng
- Browse restaurants near you, filter by cuisine, sort by distance/rating
- View menus, add items to cart, and place orders
- Checkout with delivery fee + ETA from distance and time-of-day
- Order history with live status simulation

## Project structure
```
tapngo/
├── app.py                  # entry point: simple profile + location
├── pages/
│   ├── 1_Restaurants.py    # browse + filter + sort
│   ├── 2_Menu.py           # menu + add to cart
│   ├── 3_Cart.py           # cart + checkout
│   └── 4_Orders.py         # order history + live status
├── db/
│   ├── connection.py       # Filess.io MySQL connection
│   ├── schema.py           # SQLAlchemy table definitions
│   └── seed.py             # seeds 8 Bangalore restaurants + menus
├── utils/
│   ├── geo.py              # haversine distance + RapidAPI geocoding
│   ├── pricing.py          # delivery fee + ETA logic
│   └── db_helpers.py       # all queries/inserts used by the pages
├── requirements.txt
└── .env.example
```

## Run it
```bash
pip install -r requirements.txt
copy .env.example .env
python -m db.seed
streamlit run app.py
```
1. Create a MySQL database at https://filess.io and copy its host, port,
  database name, username, and password.
2. Fill `.env.example` values into your environment or `.env` file.
3. For live address lookup, subscribe on RapidAPI to the exact API named
  `Forward & Reverse Geocoding` and keep
  `RAPIDAPI_GEO_HOST=forward-reverse-geocoding.p.rapidapi.com`.
4. Run `python -m db.seed` once to create tables and seed data.

## Notes on the "interesting" bits
- **Delivery fee**: ₹20 base + ₹5/km, computed from real haversine distance
  between your saved location and the restaurant.
- **ETA**: base prep time (15 min) + travel time, with a 15–20% surge
  multiplier during lunch (12–3pm) and dinner (7–10pm) hours.
- **Order status simulation**: rather than a fake fixed timer, status is
  derived from elapsed time as a fraction of the estimated delivery time,
  and persisted back to the DB — so refreshing the page or coming back
  later shows a consistent, advancing status.

## Notes
- The exact RapidAPI service name used for location lookup is
  `Forward & Reverse Geocoding`.
- If you are reusing an older database that still has a `password_hash`
  column, the app will ignore it. A fresh Filess.io database is the cleanest
  setup for this version.
