import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI topilmadi. .env faylida MONGODB_URI ni qo'shing.")

client = MongoClient(MONGODB_URI)
try:
    client.server_info()  # Ulanishni tekshirish
except Exception as e:
    raise RuntimeError(f"MongoDB ulanishda xatolik: {e}")

db = client.get_database("safartaxi")
users_collection = db["users"]
trips_collection = db["trips"]

def init_db():
    pass

def save_user(user_id, role, full_name, phone, car_model=None, car_color=None, car_number=None):
    user_data = {
        "user_id": user_id,
        "role": role,
        "full_name": full_name,
        "phone": phone,
        "car_model": car_model,
        "car_color": car_color,
        "car_number": car_number
    }
    users_collection.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)

def get_user(user_id):
    return users_collection.find_one({"user_id": user_id})

def save_trip(user_id, role, from_region, from_district, to_region, to_district, mahalla, price, seats, when_mode, when_date, when_time):
    trip_data = {
        "user_id": user_id,
        "role": role,
        "from_region": from_region,
        "from_district": from_district,
        "to_region": to_region,
        "to_district": to_district,
        "mahalla": mahalla,
        "price": price,
        "seats": seats,
        "when_mode": when_mode,
        "when_date": when_date,
        "when_time": when_time
    }
    trips_collection.update_one({"user_id": user_id}, {"$set": trip_data}, upsert=True)

def get_user_trip(user_id):
    return trips_collection.find_one({"user_id": user_id})

def update_seats(user_id, seats):
    trips_collection.update_one({"user_id": user_id}, {"$set": {"seats": seats}})

def delete_trip(user_id):
    trips_collection.delete_one({"user_id": user_id})

def get_matching_passengers(from_region, from_district, to_region, to_district):
    return list(trips_collection.find({
        "role": "passenger",
        "from_region": from_region,
        "from_district": from_district,
        "to_region": to_region,
        "to_district": to_district
    }))

def get_matching_drivers(from_region, from_district, to_region, to_district):
    return list(trips_collection.find({
        "role": "driver",
        "from_region": from_region,
        "from_district": from_district,
        "to_region": to_region,
        "to_district": to_district
    }))

def get_stats():
    drivers_count = users_collection.count_documents({"role": "driver"})
    passengers_count = users_collection.count_documents({"role": "passenger"})
    return drivers_count, passengers_count

def get_all_drivers():
    drivers = users_collection.find({"role": "driver"})
    return [(d["user_id"], d["full_name"], d["phone"]) for d in drivers]

def get_all_passengers():
    passengers = users_collection.find({"role": "passenger"})
    return [(p["user_id"], p["full_name"], p["phone"]) for p in passengers]