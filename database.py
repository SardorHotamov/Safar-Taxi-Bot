from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
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
except ServerSelectionTimeoutError as e:
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

def get_user(user_id: int) -> Optional[dict]:
    """Foydalanuvchi ma'lumotlarini olish."""
    user = db.users.find_one({"user_id": user_id})
    if user:
        return {
            'user_id': user['user_id'],
            'role': user['role'],
            'full_name': user['full_name'],
            'phone': user['phone'],
            'car_model': user.get('car_model'),
            'car_color': user.get('car_color'),
            'car_number': user.get('car_number')
        }
    return None

def get_stats():
    """Statistika olish."""
    user_count = db.users.count_documents({})
    driver_count = db.users.count_documents({"role": "driver"})
    passenger_count = db.users.count_documents({"role": "passenger"})
    return f"Foydalanuvchilar soni: {user_count}\nHaydovchilar soni: {driver_count}\nYo‘lovchilar soni: {passenger_count}"

def get_all_drivers():
    """Barcha haydovchilarni olish."""
    return list(db.users.find({"role": "driver"}))

def get_all_passengers():
    """Barcha yo'lovchilarni olish."""
    return list(db.users.find({"role": "passenger"}))

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
    """Foydalanuvchini o'chirish."""
    result = db.users.delete_one({"user_id": user_id})
    return result.deleted_count

def get_user_count():
    """Umumiy foydalanuvchilar soni."""
    return db.users.count_documents({})

def get_driver_count():
    """Haydovchilar soni."""
    return db.users.count_documents({"role": "driver"})

def get_passenger_count():
    """Yo‘lovchilar soni."""
    return db.users.count_documents({"role": "passenger"})

def get_all_users():
    """Barcha foydalanuvchilarni olish."""
    return list(db.users.find())

# Admin uchun xabar yuborish uchun kerak bo'lsa
def get_all_drivers_chat_ids():
    return [user['chat_id'] for user in db.users.find({"role": "driver"}, {"chat_id": 1}) if 'chat_id' in user]

def get_all_passengers_chat_ids():
    return [user['chat_id'] for user in db.users.find({"role": "passenger"}, {"chat_id": 1}) if 'chat_id' in user]

def get_all_users_chat_ids():
    return [user['chat_id'] for user in db.users.find({}, {"chat_id": 1}) if 'chat_id' in user]

# Geolokatsiya uchun haydovchilarni olish (sinov)
def get_matching_drivers(route: str) -> List[dict]:
    return [{"name": "Haydovchi 1", "chat_id": "123456789"}, {"name": "Haydovchi 2", "chat_id": "987654321"}]