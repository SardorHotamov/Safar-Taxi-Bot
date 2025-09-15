from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError  # Tuzatildi
import os
from typing import Optional, Tuple, List
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from typing import Optional

# Loglashni sozlash
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI topilmadi. .env faylida MONGODB_URI=... deb qo‘ying.")

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.server_info()  # Ulanishni tekshirish
    db = client['SafarTaxiBot']
except ServerSelectionTimeoutError as e:  # Tuzatildi
    raise RuntimeError(f"MongoDB ulanishda xatolik: {e}")

def init_db():
    logger.info("Ma'lumotlar bazasi ishga tushirilmoqda")
    # Ma'lumotlar bazasi logikasi (masalan, SQLite)
    try:
        # Bu yerda DB kodini qo‘shing (agar mavjud bo‘lsa)
        pass
    except Exception as e:
        logger.error(f"DB xatosi: {e}")
        raise

def save_user(user_id: int, role: str, full_name: str, phone: str, car_model: Optional[str] = None, car_color: Optional[str] = None, car_number: Optional[str] = None):
    """Foydalanuvchini saqlash."""
    user_data = {
        "user_id": user_id,
        "role": role,
        "full_name": full_name,
        "phone": phone,
        "car_model": car_model,
        "car_color": car_color,
        "car_number": car_number
    }
    db.users.replace_one({"user_id": user_id}, user_data, upsert=True)

def save_trip(user_id: int, role: str, from_region: str, from_district: str, to_region: str, to_district: str,
              mahalla: Optional[str], price: Optional[int], seats: str, when_mode: str, when_date: Optional[str], when_time: Optional[str]):
    """Sayohatni saqlash."""
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
    db.trips.replace_one({"user_id": user_id}, trip_data, upsert=True)

def delete_expired_trips():
    threshold = datetime.utcnow() - timedelta(hours=24)
    expired_trips = db.trips.find({"created_at": {"$lt": threshold}})
    for trip in expired_trips:
        db.users.delete_one({"user_id": trip["user_id"]})
        db.trips.delete_one({"user_id": trip["user_id"]})
    return len(list(expired_trips))

def get_user(user_id: int) -> Optional[dict]:
    """Foydalanuvchi ma'lumotlarini olish."""
    user = db.users.find_one({"user_id": user_id})
    if user:
        return {
            'user_id': user['user_id'],
            'role': user['role'],
            'full_name': user['full_name'],
            'phone': user['phone'],
            'car_model': user['car_model'],
            'car_color': user['car_color'],
            'car_number': user['car_number']
        }
    return None

def get_user_trip(user_id: int) -> Optional[dict]:
    """Foydalanuvchining sayohat ma'lumotlarini olish."""
    trip = db.trips.find_one({"user_id": user_id})
    if trip:
        return {
            'user_id': trip['user_id'],
            'role': trip['role'],
            'from_region': trip['from_region'],
            'from_district': trip['from_district'],
            'to_region': trip['to_region'],
            'to_district': trip['to_district'],
            'mahalla': trip['mahalla'],
            'price': trip['price'],
            'seats': trip['seats'],
            'when_mode': trip['when_mode'],
            'when_date': trip['when_date'],
            'when_time': trip['when_time']
        }
    return None

def get_stats() -> Tuple[int, int]:
    """Statistikani olish."""
    drivers_count = db.users.count_documents({"role": "driver"})
    passengers_count = db.users.count_documents({"role": "passenger"})
    return drivers_count, passengers_count    

def get_all_users():
    # Barcha foydalanuvchilarni olish uchun SQL yoki boshqa logikani qo‘shing
    # Masalan, haydovchilar va yo‘lovchilarni birlashtirish:
    drivers = get_all_drivers()
    passengers = get_all_passengers()
    return drivers + passengers

def get_all_drivers():
    try:
        drivers = list(db.drivers.find({}, {"_id": 0, "chat_id": 1, "name": 1}))  # Faqat kerakli maydonlar
        print(f"Haydovchilar: {drivers}")  # Debug uchun
        return drivers
    except Exception as e:
        print(f"Xatolik: {e}")
        return []

def get_all_passengers():
    try:
        passengers = list(db.passengers.find({}, {"_id": 0, "chat_id": 1, "name": 1}))
        print(f"Yo‘lovchilar: {passengers}")
        return passengers
    except Exception as e:
        print(f"Xatolik: {e}")
        return []

def get_matching_passengers(from_region: str, from_district: str, to_region: str, to_district: str) -> List[Tuple[int]]:
    """Mos yo'lovchilarni topish."""
    passengers = db.trips.find({
        "role": "passenger",
        "from_region": from_region,
        "from_district": from_district,
        "to_region": to_region,
        "to_district": to_district
    }, {"user_id": 1})
    return [(p["user_id"],) for p in passengers]

def get_matching_drivers(from_region: str, from_district: str, to_region: str, to_district: str) -> List[Tuple[int]]:
    """Mos haydovchilarni topish."""
    drivers = db.trips.find({
        "role": "driver",
        "from_region": from_region,
        "from_district": from_district,
        "to_region": to_region,
        "to_district": to_district
    }, {"user_id": 1})
    return [(d["user_id"],) for d in drivers]

def update_seats(user_id: int, seats: str):
    """Bo'sh o'rinlarni yangilash."""
    db.trips.update_one({"user_id": user_id}, {"$set": {"seats": seats}})

def delete_trip(user_id: int):
    """Sayohatni o'chirish."""
    db.trips.delete_one({"user_id": user_id})

def delete_user(user_id: int):
    result = db.users.delete_one({"user_id": user_id})
    return result.deleted_count    

def get_user_count():
    return db.users.count_documents({})  

def get_driver_count():
    return db.users.count_documents({"role": "driver"})

def get_passenger_count():
    return db.users.count_documents({"role": "passenger"})