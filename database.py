from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import os
from typing import Optional, Tuple, List
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

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

def init_db() -> None:
    """Ma'lumotlar bazasini indekslar bilan ishga tushirish."""
    logger.info("Ma'lumotlar bazasi ishga tushirilmoqda")
    db.users.create_index("user_id", unique=True)
    db.trips.create_index("user_id", unique=True)

def save_user(
    user_id: int,
    role: str,
    full_name: str,
    phone: str,
    car_model: Optional[str] = None,
    car_color: Optional[str] = None,
    car_number: Optional[str] = None
) -> None:
    """Foydalanuvchi ma'lumotlarini MongoDB'ga saqlash."""
    user_data = {
        "user_id": user_id,
        "role": role,
        "full_name": full_name,
        "phone": phone,
        "car_model": car_model,
        "car_color": car_color,
        "car_number": car_number,
#        "subscription_start_date": None,
#        "subscription_end_date": None
    }
    db.users.replace_one({"user_id": user_id}, user_data, upsert=True)
    logger.info(f"Foydalanuvchi saqlandi: user_id={user_id}")

def save_trip(
    user_id: int,
    role: str,
    from_region: str,
    from_district: str,
    to_region: str,
    to_district: str,
    mahalla: Optional[str],
    price: Optional[int],
    seats: str,
    when_mode: str,
    when_date: Optional[str],
    when_time: Optional[str]
) -> None:
    """Sayohat ma'lumotlarini MongoDB'ga saqlash."""
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
    logger.info(f"Sayohat saqlandi: user_id={user_id}")

def get_user(user_id: int) -> Optional[dict]:
    """Foydalanuvchi ma'lumotlarini MongoDB'dan olish."""
    user = db.users.find_one({"user_id": user_id})
    if user:
        return user
    logger.warning(f"Foydalanuvchi topilmadi: user_id={user_id}")
    return None

def get_stats() -> str:
    """Foydalanuvchilar statistikasini olish."""
    user_count = db.users.count_documents({})
    driver_count = db.users.count_documents({"role": "driver"})
    passenger_count = db.users.count_documents({"role": "passenger"})
    return f"Foydalanuvchilar soni: {user_count}\nHaydovchilar soni: {driver_count}\nYo‘lovchilar soni: {passenger_count}"

def get_all_drivers() -> List[dict]:
    """Barcha haydovchilarni olish."""
    try:
        drivers = list(db.users.find({"role": "driver"}))
        logger.info(f"Topilgan haydovchilar: {len(drivers)} ta")
        return drivers
    except Exception as e:
        logger.error(f"Haydovchilarni olishda xato: {e}")
        return []

def get_all_passengers() -> List[dict]:
    """Barcha yo'lovchilarni olish."""
    try:
        passengers = list(db.users.find({"role": "passenger"}))
        logger.info(f"Topilgan yo‘lovchilar: {len(passengers)} ta")
        return passengers
    except Exception as e:
        logger.error(f"Yo‘lovchilarni olishda xato: {e}")
        return []

def get_matching_passengers(from_region: str, from_district: str, to_region: str, to_district: str) -> List[Tuple[int]]:
    """Mos yo'lovchilarni MongoDB'dan topish."""
    try:
        passengers = db.trips.find({
            "role": "passenger",
            "from_region": {"$regex": f"^{from_region}$", "$options": "i"},
            "from_district": {"$regex": f"^{from_district}$", "$options": "i"},
            "to_region": {"$regex": f"^{to_region}$", "$options": "i"},
            "to_district": {"$regex": f"^{to_district}$", "$options": "i"}
        }, {"user_id": 1})
        result = [(p["user_id"],) for p in passengers]
        logger.info(f"Topilgan yo‘lovchilar: {len(result)} ta")
        return result
    except Exception as e:
        logger.error(f"Mos yo‘lovchilarni topishda xato: {e}")
        return []

def get_matching_drivers(from_region: str, from_district: str, to_region: str, to_district: str) -> List[dict]:
    """Mos haydovchilarni MongoDB'dan topish."""
    try:
        trips = db.trips.find({
            "role": "driver",
            "from_region": {"$regex": f"^{from_region}$", "$options": "i"},
            "from_district": {"$regex": f"^{from_district}$", "$options": "i"},
            "to_region": {"$regex": f"^{to_region}$", "$options": "i"},
            "to_district": {"$regex": f"^{to_district}$", "$options": "i"}
        })
        drivers = []
        for trip in trips:
            user = get_user(trip['user_id'])
            if user:
                user['trip'] = trip
                drivers.append(user)
        logger.info(f"Topilgan haydovchilar: {len(drivers)} ta")
        return drivers
    except Exception as e:
        logger.error(f"Mos haydovchilarni topishda xato: {e}")
        return []

def get_user_trip(user_id: int) -> Optional[dict]:
    """Foydalanuvchining sayohat ma'lumotlarini olish."""
    try:
        trip = db.trips.find_one({"user_id": user_id})
        if trip:
            return trip
        logger.warning(f"Sayohat topilmadi: user_id={user_id}")
        return None
    except Exception as e:
        logger.error(f"Sayohat olishda xato: {e}")
        return None

def update_seats(user_id: int, seats: str) -> None:
    """Bo'sh o'rinlarni yangilash."""
    db.trips.update_one({"user_id": user_id}, {"$set": {"seats": seats}})
    logger.info(f"O‘rinlar yangilandi: user_id={user_id}, seats={seats}")

def delete_trip(user_id: int) -> None:
    """Sayohatni o'chirish."""
    db.trips.delete_one({"user_id": user_id})
    logger.info(f"Sayohat o‘chirildi: user_id={user_id}")

def delete_user(user_id: int) -> int:
    """Foydalanuvchi va uning sayohatini o'chirish."""
    result = db.users.delete_one({"user_id": user_id})
    db.trips.delete_one({"user_id": user_id})
    logger.info(f"Foydalanuvchi o‘chirildi: user_id={user_id}")
    return result.deleted_count

def get_user_count() -> int:
    """Umumiy foydalanuvchilar soni."""
    return db.users.count_documents({})

def get_driver_count() -> int:
    """Haydovchilar soni."""
    return db.users.count_documents({"role": "driver"})

def get_passenger_count() -> int:
    """Yo‘lovchilar soni."""
    return db.users.count_documents({"role": "passenger"})

def get_all_users() -> List[dict]:
    """Barcha foydalanuvchilarni olish."""
    return list(db.users.find())

def get_all_drivers_chat_ids() -> List[int]:
    """Barcha haydovchilarning user_id larini olish."""
    return [user['user_id'] for user in db.users.find({"role": "driver"})]

def get_all_passengers_chat_ids() -> List[int]:
    """Barcha yo'lovchilarning user_id larini olish."""
    return [user['user_id'] for user in db.users.find({"role": "passenger"})]

def get_all_users_chat_ids() -> List[int]:
    """Barcha foydalanuvchilarning user_id larini olish."""
    return [user['user_id'] for user in db.users.find()]

#def has_active_subscription(user_id: int) -> bool:
#    """Foydalanuvchining faol obunasi borligini tekshirish."""
#    user = db.users.find_one({"user_id": user_id})
#    if not user or user.get('role') != 'driver':
#        return False
#    end_date = user.get('subscription_end_date')
#    if end_date and end_date > datetime.now():
#        return True
#    return False

#def init_free_trial(user_id: int) -> None:
#    """Haydovchi uchun 5 kunlik bepul sinov muddatini boshlash."""
#    db.users.update_one({"user_id": user_id}, {"$set": {
#        "subscription_start_date": datetime.now(),
#        "subscription_end_date": datetime.now() + timedelta(days=5)
#    }})
#    logger.info(f"Bepul sinov boshlandi: user_id={user_id}")

#def update_subscription(user_id: int, duration_days: int) -> None:
#    """Obuna muddatini yangilash."""
#    end_date = datetime.now() + timedelta(days=duration_days)
#    db.users.update_one({"user_id": user_id}, {"$set": {"subscription_end_date": end_date}})
#    logger.info(f"Obuna yangilandi: user_id={user_id}, end_date={end_date}")

def delete_expired_trips() -> int:
    """Muddat o'tgan sayohatlarni o'chirish."""
    expired = db.trips.delete_many({"when_date": {"$lt": datetime.now() - timedelta(hours=24)}})
    logger.info(f"Muddat o‘tgan sayohatlar o‘chirildi: {expired.deleted_count} ta")
    return expired.deleted_count