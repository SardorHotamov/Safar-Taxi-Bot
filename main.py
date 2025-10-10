import schedule
import time
import asyncio
import os
from datetime import datetime, timedelta
import requests
import base64
import json
import logging
from typing import str

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Flask app webhook uchun
flask_app = Flask(__name__)

# ------------------ DATABASE IMPORTS ------------------
from database import (
    init_db,
    get_user,
    get_stats,
    get_all_drivers,
    get_all_passengers,
    get_matching_passengers,
    get_matching_drivers,
    get_user_trip,
    save_user,
    save_trip,
    update_seats,
    delete_trip,
    has_active_subscription,
    init_free_trial,
    update_subscription,
)

# Loglashni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------ REGIONS (import) ------------------
from regions import regions

# ------------------ UTILS ------------------
from utils import is_valid_date, format_date, format_time

from telegram import Update
from telegram.ext import ContextTypes
from database import get_all_users, get_all_drivers, get_all_passengers

# ------------------ ENV ------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 10000))
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY")
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID")
PAYME_SECRET_KEY = os.getenv("PAYME_SECRET_KEY")

if not BOT_TOKEN or not WEBHOOK_URL:
    logger.error("BOT_TOKEN yoki WEBHOOK_URL noto‘g‘ri belgilangan!")
    raise ValueError("BOT_TOKEN yoki WEBHOOK_URL noto‘g‘ri belgilangan!")
if not CLICK_MERCHANT_ID or not CLICK_SECRET_KEY or not PAYME_MERCHANT_ID or not PAYME_SECRET_KEY:
    logger.error("To‘lov tizimlari uchun env o‘zgaruvchilari topilmadi!")
    raise ValueError("CLICK yoki PAYME sozlamalari noto‘g‘ri!")

ADMIN_IDS = set()
env_admins = os.getenv("ADMINS", "")
if env_admins:
    ADMIN_IDS = {int(x.strip()) for x in env_admins.split(",") if x.strip().isdigit()}

# ------------------ TEXT LABELS ------------------
BTN_DRIVER = "Haydovchi"
BTN_PASSENGER = "Yo‘lovchi"
BTN_CHOOSE_ROUTE = "Yo‘nalish tanlash"
BTN_EDIT_PROFILE = "Profilni tahrirlash"
BTN_HELP = "Yordam"

BTN_SEE_PASSENGERS = "Yo‘lovchilarni ko‘rish"
BTN_CHANGE_SEATS = "Bo‘sh joylar soni"
BTN_GO = "Ketdik"

BTN_SEE_DRIVERS = "Haydovchilarni ko‘rish"
SELECT_DRIVER = "Haydivchini tanlash"
BTN_SEND_GEO = "Geolokatsiya yuborish"

BTN_BACK = "Orqaga"
BTN_BACK_TO_MENU = "Asosiy menyu"
BTN_NOW = "Hozir"
BTN_PLAN = "Rejalashtirish"
BTN_TODAY = "Bugun"
BTN_TOMORROW = "Ertaga"
BTN_OTHER_DATE = "Boshqa sana"
BTN_POST = "Pochta"

# Admin tugmalari konstantalari
BTN_ADMIN_STATS = "Foydalanuvchilar soni"
BTN_ADMIN_DRIVERS = "Haydovchilar ma'lumotlari"
BTN_ADMIN_PASSENGERS = "Yo‘lovchilar ma'lumotlari"
SEND_TO_ALL_GROUPS = "Barchaga xabar yuborish"
SEND_TO_DRIVERS = "Haydovchilarga xabar"
SEND_TO_PASSENGERS = "Yo‘lovchilarga xabar"
BTN_ADMIN_REPLY = "Xabar yuborish"
BTN_DELETE_USER_PROMPT = "Foydalanuvchini o‘chirish"
BTN_ADMIN_ADVERT = "Reklama joylash"

SEATS_BUTTONS = ["1", "2", "3", "4", "5", "6"]

# ------------------ STATES ------------------
(
    CHOOSE_ROLE,
    REGISTER_NAME,
    REGISTER_PHONE,
    REGISTER_CAR_MODEL,
    REGISTER_CAR_COLOR,
    REGISTER_CAR_NUMBER,

    FROM_REGION,
    FROM_DISTRICT,
    FROM_AREA,
    TO_REGION,
    TO_DISTRICT,
    ENTER_PRICE,
    CHOOSE_SEATS,
    WHEN,
    WHEN_PLAN_DATE,
    WHEN_PLAN_HOUR,

    AFTER_ROUTE_MENU,
    HELP_MESSAGE,
    CHANGE_SEATS_STATE,
    ADMIN_MENU,
    ADMIN_REPLY,
    SUBSCRIPTION_STATE,  # Yangi state
    PAYMENT_METHOD_STATE,
    ADVERT_MESSAGE,
) = range(24)

# ------------------ HELPERS: KEYBOARDS ------------------
from keyboards import (
    role_keyboard,
    phone_keyboard,
    main_menu_driver,
    main_menu_passenger,
    post_route_menu_driver,
    post_route_menu_passenger,
    regions_keyboard,
    districts_keyboard,
    seats_keyboard,
    when_keyboard,
    date_keyboard,
    hour_keyboard,
    admin_menu_keyboard,
)

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(BTN_DRIVER), KeyboardButton(BTN_PASSENGER)],
        [KeyboardButton(BTN_CHOOSE_ROUTE), KeyboardButton(BTN_EDIT_PROFILE)],
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_BACK)]], resize_keyboard=True)

def subscription_keyboard() -> ReplyKeyboardMarkup:
    """Obuna turlari klaviaturasini yaratish."""
    return ReplyKeyboardMarkup([
        ["1 kunlik (3000 so'm)", "10 kunlik (20000 so'm)"],
        ["1 oylik (40000 so'm)", "6 oylik (180000 so'm)"],
        ["1 yillik (320000 so'm)", BTN_BACK]
    ], resize_keyboard=True)

def payment_method_keyboard() -> ReplyKeyboardMarkup:
    """To‘lov usullari klaviaturasini yaratish."""
    return ReplyKeyboardMarkup([
        ["Click orqali to'lov", "Payme orqali to'lov"],
        [BTN_BACK]
    ], resize_keyboard=True)

def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    """Admin menyu klaviaturasini yaratish."""
    keyboard = [
        [KeyboardButton(BTN_ADMIN_STATS), KeyboardButton(BTN_ADMIN_DRIVERS)],
        [KeyboardButton(BTN_ADMIN_PASSENGERS), KeyboardButton(BTN_ADMIN_REPLY)],
        [KeyboardButton(SEND_TO_ALL_GROUPS), KeyboardButton(SEND_TO_DRIVERS)],
        [KeyboardButton(SEND_TO_PASSENGERS), KeyboardButton(BTN_ADMIN_ADVERT)],
        [KeyboardButton(BTN_DELETE_USER_PROMPT), KeyboardButton(BTN_BACK)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ------------------ HELPERS: COMMON ------------------
def is_valid_phone(p: str) -> bool:
    if not p:
        return False
    digits = "".join(ch for ch in p if ch.isdigit() or ch == "+")
    return digits.startswith("+998") and len(digits) in (13, 12)

def is_valid_license(txt: str) -> bool:
    t = (txt or "").strip().upper()
    return 7 <= len(t) <= 10

def show_main_menu_by_role(user_role: str):
    return main_menu_driver() if user_role == "driver" else main_menu_passenger()

def normalize_phone(p: str) -> str:
    p = p.replace(" ", "").replace("-", "")
    if p.startswith("998"):
        p = "+" + p
    return p

def format_trip_info(trip):
    if not trip:
        return "Yo'nalish ma'lumotlari topilmadi."
    when = "Hozir" if trip['when_mode'] == 'now' else f"{trip['when_date']} {trip['when_time']}"
    price_str = f"{trip['price']} so'm" if trip['price'] else ""
    seats_str = "Pochta" if trip['seats'] == "post" else f"{trip['seats']} ta {'bo‘sh o‘rin' if trip['role'] == 'driver' else 'yo‘lovchi'}"
    mahalla_str = f", {trip['mahalla']}" if trip['mahalla'] else ""
    return (f"Yo'nalish tanlandi:\n"
            f"Qayerdan?: {trip['from_region']}, {trip['from_district']}{mahalla_str}\n"
            f"Qayerga?: {trip['to_region']}, {trip['to_district']}\n"
            f"Qachon?: {when}\n"
            f"Narx: {price_str}\n"
            f"🪑 {seats_str}")

def format_match_info(user, trip, is_driver):
    full_name, phone = user['full_name'], user['phone']
    from_region, from_district, to_region, to_district = trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district']
    mahalla, when_mode, when_date, when_time = trip['mahalla'], trip['when_mode'], trip['when_date'], trip['when_time']
    seats = trip['seats']
    when = "Hozir" if when_mode == 'now' else f"{when_date} {when_time}"
    mahalla_str = f", {mahalla}" if mahalla else ""
    direction = (f"Yangi {'haydovchi' if is_driver else 'yo‘lovchi'}:\n"
                f"Qayerdan?: {from_region}, {from_district}{mahalla_str}\n"
                f"Qayerga?: {to_region}, {to_district}\n"
                f"Qachon?: {when}")
    if is_driver:
        car_model, car_color, car_number, price = user['car_model'], user['car_color'], user['car_number'], trip['price']
        seats_str = "Pochta" if seats == "post" else f"{seats} bo‘sh o‘rin"
        return (f"{direction}\n"
                f"👤 {full_name}\n"
                f"📞 {phone}\n"
                f"🚘 {car_model}, {car_color}, {car_number}\n"
                f"💵 {price if price else 'Kelishiladi'} so‘m\n"
                f"🪑 {seats_str}")
    else:
        seats_str = "Pochta" if seats == "post" else f"{seats} ta yo‘lovchi"
        return (f"{direction}\n"
                f"👤 {full_name}\n"
                f"📞 {phone}\n"
                f"🪑 {seats_str}")

# ------------------ PAYMENT FUNCTIONS ------------------
def generate_payment_url_click(user_id: int, amount: int, description: str) -> str:
    """Click orqali to'lov URL generatsiya qilish."""
    try:
        params = {
            "merchant_id": CLICK_MERCHANT_ID,
            "amount": amount,
            "transaction_param": f"user_{user_id}_{description.replace(' ', '_')}",
            "return_url": WEBHOOK_URL + "/payment_success",
            "callback_url": WEBHOOK_URL + "/payment_callback_click"
        }
        response = requests.post("https://api.click.uz/v2/merchant/invoice/create", json=params, headers={"Authorization": f"Bearer {CLICK_SECRET_KEY}"})
        if response.status_code == 200:
            return response.json().get('invoice_url', 'Xato: URL topilmadi')
        logger.error(f"Click API xatosi: {response.status_code} - {response.text}")
        return f"To'lov URL yaratishda xato: HTTP {response.status_code}"
    except Exception as e:
        logger.error(f"Click to'lov URL yaratishda xato: {e}")
        return f"To'lov URL yaratishda xato: {str(e)}"

def generate_payment_url_payme(user_id: int, amount: int, description: str) -> str:
    """Payme orqali to'lov URL generatsiya qilish."""
    try:
        merchant_id = PAYME_MERCHANT_ID
        secret_key = PAYME_SECRET_KEY
        callback_url = WEBHOOK_URL + "/payment_callback_payme"
        amount_in_tiyin = amount * 100
        order_id = f"user_{user_id}_{description.replace(' ', '_')}"
        payload = {
            "method": "CreateTransaction",
            "params": {
                "account": {"order_id": order_id},
                "amount": amount_in_tiyin,
                "currency": "UZS",
                "detail": {
                    "title": description,
                    "description": f"Obuna: {description} for user {user_id}"
                },
                "callback_url": callback_url
            }
        }
        auth_string = f"{merchant_id}:{secret_key}"
        auth_header = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_header}"
        }
        response = requests.post(
            "https://checkout.paycom.uz/api",
            json=payload,
            headers=headers
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("result") and result["result"].get("create_transaction"):
                transaction_id = result["result"]["create_transaction"]["transaction"]
                return f"https://payme.uz/checkout/{transaction_id}"
            logger.error(f"Payme xatosi: {result.get('error')}")
            return f"To'lov URL yaratishda xato: {result.get('error', 'Noma’lum xato')}"
        logger.error(f"Payme API xatosi: {response.status_code} - {response.text}")
        return f"To'lov URL yaratishda xato: HTTP {response.status_code}"
    except Exception as e:
        logger.error(f"Payme to'lov URL yaratishda xato: {e}")
        return f"To'lov URL yaratishda xato: {str(e)}"

# ------------------ HANDLERS: START ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    saved_user = get_user(user_id)
    if not saved_user:
        await update.message.reply_text(
        "Safar Taxi botiga xush kelibsiz!\n\n"
        " Haydovchi sifatida siz:\n"
        "  • Ro‘yxatdan o‘tasiz\n"
        "  • Avtomobilingiz va telefon raqamingizni kiritasiz\n"
        "  • Qayerdan qayerga borishingizni belgilaysiz\n"
        "  • Narxni va bo’sh joylar sonini (yoki pochta) belgilaysiz\n\n"
        " Yo‘lovchi sifatida siz:\n"
        "  • Ro‘yxatdan o‘tasiz\n"
        "  • Manzilingizni tanlaysiz\n"
        "  • Yo’lovchilar sonini yoki pochta yuborishni belgilaysiz\n"
        "  • Haydovchilar ro‘yxatini ko‘rib chiqasiz\n"
        "  • Mosini tanlab, telefon orqali bog‘lanasiz\n\n",
            reply_markup=ReplyKeyboardMarkup([["Haydovchi", "Yo‘lovchi"]], resize_keyboard=True)
        )
        return CHOOSE_ROLE  # To‘g‘ri state
    await update.message.reply_text(
        f"Assalomu alaykum, {saved_user['full_name']}!\n"
        "Siz allaqachon ro‘yxatdan o‘tgansiz. Quyidagilardan birini tanlang",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        return await start(update, context)
    if txt not in [BTN_DRIVER, BTN_PASSENGER]:
        await update.message.reply_text("Haydovchi yoki Yo‘lovchi tanlang:", reply_markup=role_keyboard())
        return CHOOSE_ROLE
    role = "driver" if txt == BTN_DRIVER else "passenger"
    context.user_data['role'] = role
    await update.message.reply_text("Ismingiz va familiyangizni kiriting:", reply_markup=back_keyboard())
    return REGISTER_NAME

async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Quyidagilardan birini tanlang:", reply_markup=role_keyboard())
        return CHOOSE_ROLE
    if len(txt) < 3:
        await update.message.reply_text("Ism va familiya kamida 3 harfdan iborat bo‘lsin:", reply_markup=back_keyboard())
        return REGISTER_NAME
    context.user_data['full_name'] = txt
    await update.message.reply_text("Telefon raqamingizni (+998XXYYYYYYY formatida) yozing yoki quyidagi tugma orqali yuboring:", reply_markup=phone_keyboard())
    return REGISTER_PHONE

async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        p = update.message.contact.phone_number
    else:
        p = update.message.text
    if p == BTN_BACK:
        await update.message.reply_text("Ismingiz va familiyangizni kiriting:", reply_markup=back_keyboard())
        return REGISTER_NAME
    if not is_valid_phone(p):
        await update.message.reply_text("To‘g‘ri telefon raqamini kiriting (masalan, +998901234567):", reply_markup=phone_keyboard())
        return REGISTER_PHONE
    context.user_data['phone'] = normalize_phone(p)
    role = context.user_data.get('role')
    if role == "driver":
        await update.message.reply_text("Avtomobil modelini kiriting (Nexia 3, Gentra, Cobalt):", reply_markup=back_keyboard())
        return REGISTER_CAR_MODEL
    else:
        save_user(update.effective_user.id, role, context.user_data['full_name'], context.user_data['phone'])
        await update.message.reply_text("Tabriklaymiz! Siz yo'lovchi sifatida muvaffaqiyatli ro‘yxatdan o‘tdingiz! Endi yo‘nalish tanlashingiz mumkin.", reply_markup=main_menu_passenger())
        return ConversationHandler.END

async def register_car_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
        return REGISTER_PHONE
    context.user_data['car_model'] = txt
    await update.message.reply_text("Avtomobil rangini kiriting (Oq, Qora):", reply_markup=back_keyboard())
    return REGISTER_CAR_COLOR

async def register_car_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Avtomobil modelini kiriting (Nexia 3, Gentra, Cobalt):", reply_markup=back_keyboard())
        return REGISTER_CAR_MODEL
    context.user_data['car_color'] = txt
    await update.message.reply_text("Avtomobil davlat raqamini kiriting (masalan, 01A123BC):", reply_markup=back_keyboard())
    return REGISTER_CAR_NUMBER

async def register_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Avtomobil rangini kiriting (Oq, Qora):", reply_markup=back_keyboard())
        return REGISTER_CAR_COLOR
    if not is_valid_license(txt):
        await update.message.reply_text("Avtomobil raqami 7—10 belgidagi bo‘lsin:", reply_markup=back_keyboard())
        return REGISTER_CAR_NUMBER
    context.user_data['car_number'] = txt.upper()
    save_user(
        update.effective_user.id,
        context.user_data['role'],
        context.user_data['full_name'],
        context.user_data['phone'],
        context.user_data['car_model'],
        context.user_data['car_color'],
        context.user_data['car_number']
    )
    init_free_trial(update.effective_user.id)  # 5 kunlik bepul trial
    await update.message.reply_text(
        "Tabriklaymiz! Siz haydovchi sifatida muvaffaqiyatli ro‘yxatdan o‘tdingiz! "
        "Dastlabki 5 kun bepul obuna faollashtirildi. Endi yo‘nalish tanlashingiz mumkin.",
        reply_markup=main_menu_driver()
    )
    return ConversationHandler.END

# ------------------ EDIT PROFILE ------------------
async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Profilni tahrirlash: Haydovchi yoki yo‘lovchini tanlang:", reply_markup=role_keyboard())
    return CHOOSE_ROLE

# ------------------ CHOOSE ROUTE ------------------
async def choose_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Iltimos, avval ro‘yxatdan o‘ting.", reply_markup=role_keyboard())
        return CHOOSE_ROLE
    if user['role'] == 'driver' and not has_active_subscription(update.effective_user.id):
        await update.message.reply_text("Obunangiz tugagan. Yangi obuna tanlang:", reply_markup=subscription_keyboard())
        return SUBSCRIPTION_STATE
    context.user_data['role'] = user['role']
    await update.message.reply_text("Qayerdan ketasiz? Viloyatni tanlang:", reply_markup=regions_keyboard())
    return FROM_REGION    

async def from_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    user_id = update.effective_user.id
    if txt == BTN_BACK:
        if user_id in ADMIN_IDS:
            await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
            return ADMIN_MENU
        user = get_user(user_id)
        if user:
            await update.message.reply_text("Profil menyusi:", reply_markup=show_main_menu_by_role(user['role']))
            return ConversationHandler.END
        return await start(update, context)
    if txt not in regions:
        await update.message.reply_text("Iltimos, ro‘yxatdan viloyatni tanlang:", reply_markup=regions_keyboard())
        return FROM_REGION
    context.user_data['from_region'] = txt
    await update.message.reply_text(f"{txt} ichida qaysi tumanni tanlaysiz?", reply_markup=districts_keyboard(txt))
    return FROM_DISTRICT

async def from_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Viloyatni tanlang:", reply_markup=regions_keyboard())
        return FROM_REGION
    region = context.user_data.get('from_region')
    if not region or txt not in regions.get(region, []):
        await update.message.reply_text(f"{region} ichida tumanni tanlang:", reply_markup=districts_keyboard(region))
        return FROM_DISTRICT
    context.user_data['from_district'] = txt
    await update.message.reply_text("Mahalla yoki aniq manzilni kiriting:", reply_markup=back_keyboard())
    return FROM_AREA

async def from_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Tumanni tanlang:", reply_markup=districts_keyboard(context.user_data['from_region']))
        return FROM_DISTRICT
    context.user_data['mahalla'] = txt if txt and txt != BTN_BACK else None
    await update.message.reply_text("Qayerga borasiz? Viloyatni tanlang:", reply_markup=regions_keyboard())
    return TO_REGION

async def to_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Mahalla yoki aniq manzilni kiriting:", reply_markup=back_keyboard())
        return FROM_AREA
    if txt not in regions:
        await update.message.reply_text("Viloyatni tanlang:", reply_markup=regions_keyboard())
        return TO_REGION
    context.user_data['to_region'] = txt
    await update.message.reply_text(f"{txt} ichida qaysi tumanni tanlaysiz?", reply_markup=districts_keyboard(txt))
    return TO_DISTRICT

async def to_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Viloyatni tanlang:", reply_markup=regions_keyboard())
        return TO_REGION
    region = context.user_data.get('to_region')
    if not region or txt not in regions.get(region, []):
        await update.message.reply_text(f"{region} ichida tumanni tanlang:", reply_markup=districts_keyboard(region))
        return TO_DISTRICT
    context.user_data['to_district'] = txt
    role = context.user_data.get('role')
    if role == "driver":
        await update.message.reply_text("Narxni kiriting (so‘mda, ixtiyoriy):", reply_markup=back_keyboard())
        return ENTER_PRICE
    else:
        await update.message.reply_text("Yo‘lovchilar sonini yoki pochta jo‘natishni tanlang:", reply_markup=seats_keyboard())
        return CHOOSE_SEATS

async def enter_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Tumanni tanlang:", reply_markup=districts_keyboard(context.user_data['to_region']))
        return TO_DISTRICT
    try:
        price = int(txt) if txt and txt.isdigit() else None
        if price and price < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Iltimos, to‘g‘ri narx kiriting (musbat raqam yoki o‘tkazib yuboring):", reply_markup=back_keyboard())
        return ENTER_PRICE
    context.user_data['price'] = price
    await update.message.reply_text("Bo‘sh o‘rinlar sonini yoki pochtani tanlang:", reply_markup=seats_keyboard())
    return CHOOSE_SEATS

async def choose_seats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        role = context.user_data.get('role')
        if role == "driver":
            await update.message.reply_text("Narxni kiriting:", reply_markup=back_keyboard())
            return ENTER_PRICE
        else:
            await update.message.reply_text("Tumanni tanlang:", reply_markup=districts_keyboard(context.user_data['to_region']))
            return TO_DISTRICT
    if txt == BTN_POST:
        context.user_data['seats'] = "post"
        await update.message.reply_text("Qachon ketasiz?", reply_markup=when_keyboard())
        return WHEN
    if txt not in SEATS_BUTTONS:
        await update.message.reply_text("1 dan 6 gacha son tanlang yoki Pochta tugmasini bosing:", reply_markup=seats_keyboard())
        return CHOOSE_SEATS
    context.user_data['seats'] = txt
    await update.message.reply_text("Qachon ketasiz?", reply_markup=when_keyboard())
    return WHEN

async def when_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Yo‘lovchilar sonini yoki pochta jo‘natishni tanlang:", reply_markup=seats_keyboard())
        return CHOOSE_SEATS
    if txt not in [BTN_NOW, BTN_PLAN]:
        await update.message.reply_text("Hozir yoki Rejalashtirishni tanlang:", reply_markup=when_keyboard())
        return WHEN
    context.user_data['when_mode'] = 'now' if txt == BTN_NOW else 'plan'
    if txt == BTN_NOW:
        await save_and_notify(update, context)
        return AFTER_ROUTE_MENU
    else:
        await update.message.reply_text("Sanani tanlang:\n Eslatib o‘tamiz, tanlagan yo‘nalishingiz 24 soatdan keyin bekor qilinadi", reply_markup=date_keyboard())
        return WHEN_PLAN_DATE

async def when_plan_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Qachon ketasiz?", reply_markup=when_keyboard())
        return WHEN
    today = datetime.now()
    if txt == BTN_TODAY:
        context.user_data['when_date'] = format_date(today)
    elif txt == BTN_TOMORROW:
        context.user_data['when_date'] = format_date(today + timedelta(days=1))
    elif txt == BTN_OTHER_DATE:
        await update.message.reply_text("Sanani kiriting (YYYY-MM-DD, masalan: 2025-08-18):", reply_markup=back_keyboard())
        return WHEN_PLAN_DATE
    else:
        if not is_valid_date(txt):
            await update.message.reply_text("Sanani to‘g‘ri kiriting (YYYY-MM-DD):", reply_markup=date_keyboard())
            return WHEN_PLAN_DATE
        try:
            input_date = datetime.strptime(txt, "%Y-%m-%d")
            if input_date < today:
                await update.message.reply_text("O‘tgan sanani tanlab bo‘lmaydi. Iltimos, bugun yoki undan keyingi sanani tanlang:", reply_markup=date_keyboard())
                return WHEN_PLAN_DATE
            context.user_data['when_date'] = txt
        except ValueError:
            await update.message.reply_text("Sanani to‘g‘ri kiriting (YYYY-MM-DD):", reply_markup=date_keyboard())
            return WHEN_PLAN_DATE
    await update.message.reply_text("Soatni tanlang:", reply_markup=hour_keyboard())
    return WHEN_PLAN_HOUR

async def when_plan_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Sanani tanlang:", reply_markup=date_keyboard())
        return WHEN_PLAN_DATE
    if not txt.endswith(":00") or len(txt) != 5:
        await update.message.reply_text("Soatni HH:00 formatida tanlang (masalan, 14:00):", reply_markup=hour_keyboard())
        return WHEN_PLAN_HOUR
    try:
        hour = int(txt.split(":")[0])
        if not 0 <= hour <= 23:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Soatni 00:00 dan 23:00 gacha tanlang:", reply_markup=hour_keyboard())
        return WHEN_PLAN_HOUR
    context.user_data['when_time'] = txt
    await save_and_notify(update, context)
    return AFTER_ROUTE_MENU

async def save_and_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role = context.user_data.get('role')
    if not role:
        await update.message.reply_text("Xatolik: Rol tanlanmagan. Iltimos, qaytadan boshlang.", reply_markup=role_keyboard())
        return CHOOSE_ROLE
    price = context.user_data.get('price') if role == "driver" else None
    when_mode = context.user_data.get('when_mode')
    when_date = context.user_data.get('when_date') if when_mode == 'plan' else None
    when_time = context.user_data.get('when_time') if when_mode == 'plan' else None
    seats = context.user_data.get('seats')
    try:
        save_trip(
            user_id,
            role,
            context.user_data['from_region'],
            context.user_data['from_district'],
            context.user_data['to_region'],
            context.user_data['to_district'],
            context.user_data.get('mahalla'),
            price,
            seats,
            when_mode,
            when_date,
            when_time
        )
    except Exception as e:
        await update.message.reply_text(f"Yo‘nalishni saqlashda xato yuz berdi: {e}. Iltimos, qaytadan urinib ko‘ring.")
        return ConversationHandler.END
    trip = get_user_trip(user_id)
    if not trip:
        await update.message.reply_text("Yo‘nalish saqlanmadi. Iltimos, qaytadan urinib ko‘ring.")
        return ConversationHandler.END
    await update.message.reply_text(format_trip_info(trip))
    rm = post_route_menu_driver() if role == "driver" else post_route_menu_passenger()
    await update.message.reply_text("Safar boshlanganida Ketdik tugmasini bosishni unutmang\n Quyidagi tugmalardan foydalaning", reply_markup=rm)
    # Notify matching users
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Foydalanuvchi ma'lumotlari topilmadi.")
        return ConversationHandler.END
    if role == "driver":
        matches = get_matching_passengers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
        for m in matches:
            match_id = m[0]
            match_user = get_user(match_id)
            if not match_user:
                continue
            try:
                await context.bot.send_message(
                    chat_id=match_id,
                    text=f"Yangi haydovchi qo'shildi:\n{format_match_info(user, trip, is_driver=True)}"
                )
            except Exception as e:
                print(f"Xato yuborishda (yo'lovchi {match_id}): {e}")
    else:
        matches = get_matching_drivers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
        for m in matches:
            match_id = m[0]
            match_user = get_user(match_id)
            if not match_user:
                continue
            try:
                await context.bot.send_message(
                    chat_id=match_id,
                    text=f"Yangi yo'lovchi qo'shildi:\n{format_match_info(user, trip, is_driver=False)}"
                )
            except Exception as e:
                print(f"Xato yuborishda (haydovchi {match_id}): {e}")

# ------------------ SUBSCRIPTION HANDLERS ------------------
async def handle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obuna turini tanlash."""
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Asosiy menyu:", reply_markup=main_menu_driver())
        return ConversationHandler.END
    durations = {
        "1 kunlik (3000 so'm)": (1, 3000),
        "10 kunlik (20000 so'm)": (10, 20000),
        "1 oylik (40000 so'm)": (30, 40000),
        "6 oylik (180000 so'm)": (180, 180000),
        "1 yillik (320000 so'm)": (365, 320000)
    }
    if txt not in durations:
        await update.message.reply_text("To‘g‘ri obuna turini tanlang:", reply_markup=subscription_keyboard())
        return SUBSCRIPTION_STATE
    context.user_data['subscription_type'] = txt
    context.user_data['subscription_days'] = durations[txt][0]
    context.user_data['subscription_amount'] = durations[txt][1]
    await update.message.reply_text("To‘lov usulini tanlang:", reply_markup=payment_method_keyboard())
    return PAYMENT_METHOD_STATE

async def handle_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """To'lov usulini tanlash va URL generatsiya qilish."""
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Obuna turini tanlang:", reply_markup=subscription_keyboard())
        return SUBSCRIPTION_STATE
    if txt not in ["Click orqali to'lov", "Payme orqali to'lov"]:
        await update.message.reply_text("To‘g‘ri to‘lov usulini tanlang:", reply_markup=payment_method_keyboard())
        return PAYMENT_METHOD_STATE
    method = "click" if txt == "Click orqali to'lov" else "payme"
    subscription_type = context.user_data.get('subscription_type')
    amount = context.user_data.get('subscription_amount')
    if not subscription_type or not amount:
        await update.message.reply_text("Xatolik: Obuna turi tanlanmagan. Qaytadan boshlang.", reply_markup=subscription_keyboard())
        return SUBSCRIPTION_STATE
    payment_url = generate_payment_url_click(update.effective_user.id, amount, subscription_type) if method == "click" else generate_payment_url_payme(update.effective_user.id, amount, subscription_type)
    await update.message.reply_text(
        f"{subscription_type} obuna uchun to‘lov: {amount} so‘m.\n"
        f"To‘lov linki: {payment_url}",
        reply_markup=main_menu_driver()
    )
    return ConversationHandler.END

# ------------------ AFTER ROUTE MENU ------------------
async def after_route_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    user_id = update.effective_user.id
    trip = get_user_trip(user_id)
    role = trip['role'] if trip else context.user_data.get('role')
    if not role:
        await update.message.reply_text("Xatolik: Rol topilmadi. Iltimos, qaytadan boshlang.", reply_markup=role_keyboard())
        return CHOOSE_ROLE
    if txt == BTN_BACK:
        if user_id in ADMIN_IDS:
            await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
            return ADMIN_MENU
        user = get_user(user_id)
        if user:
            await update.message.reply_text("Profil menyusi:", reply_markup=show_main_menu_by_role(user['role']))
            return ConversationHandler.END
        return await start(update, context)
    if role == "driver":
        if txt == BTN_SEE_PASSENGERS:
            return await see_passengers(update, context)
        elif txt == BTN_CHANGE_SEATS:
            await update.message.reply_text("Yangi bo‘sh o‘rinlar sonini yoki pochtani tanlang:", reply_markup=seats_keyboard())
            return CHANGE_SEATS_STATE
        elif txt == BTN_GO:
            delete_trip(user_id)
            await update.message.reply_text("Oq yo‘l! Sizga yordam berganimizdan xursandmiz", reply_markup=main_menu_driver())
            return ConversationHandler.END
    else:
        if txt == BTN_SEE_DRIVERS:
    trip = get_user_trip(user_id)
    if not trip:
        await update.message.reply_text("Yo‘nalish ma'lumotlari topilmadi.", reply_markup=post_route_menu_passenger())
        return AFTER_ROUTE_MENU
    matches = get_matching_drivers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
    if not matches:
        await update.message.reply_text("Mos haydovchilar topilmadi.", reply_markup=post_route_menu_passenger())
        return AFTER_ROUTE_MENU
    for m in matches:
        # m allaqachon full user dict, trip qo'shilgan
        await update.message.reply_text(format_match_info(m, m['trip'], is_driver=True))
    await update.message.reply_text("Quyidagi tugmalardan foydalaning", reply_markup=post_route_menu_passenger())
    return AFTER_ROUTE_MENU

# ------------------ SEE PASSENGERS / DRIVERS ------------------
async def see_passengers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    trip = get_user_trip(user_id)
    if not trip:
        await update.message.reply_text("Yo‘nalish topilmadi. Iltimos, yo‘nalish tanlang.")
        return await choose_route(update, context)
    try:
        matches = get_matching_passengers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
        if not matches:
            await update.message.reply_text("Kechirasiz, siz tanlagan yo‘nalish bo‘yicha hozircha yo‘lovchi topilmadi. Yo‘lovchi kelganda sizga xabar yuboramiz", reply_markup=post_route_menu_driver())
            return AFTER_ROUTE_MENU
        lines = []
        for m in matches:
            match_user = get_user(m[0])
            if match_user:
                match_trip = get_user_trip(m[0])
                if match_trip:
                    lines.append(format_match_info(match_user, match_trip, is_driver=False))
        if not lines:
            await update.message.reply_text("Kechirasiz, mos yo‘lovchilar topilmadi.", reply_markup=post_route_menu_driver())
            return AFTER_ROUTE_MENU
        await update.message.reply_text("\n\n".join(lines), reply_markup=post_route_menu_driver())
    except Exception as e:
        await update.message.reply_text(f"Yo‘lovchilarni ko‘rishda xato: {e}. Iltimos, qaytadan urinib ko‘ring.", reply_markup=post_route_menu_driver())
        return AFTER_ROUTE_MENU

async def see_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    trip = get_user_trip(user_id)
    if not trip:
        await update.message.reply_text("Yo‘nalish topilmadi. Iltimos, yo‘nalish tanlang.")
        return await choose_route(update, context)
    try:
        matches = get_matching_drivers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
        if not matches:
            await update.message.reply_text("Kechirasiz, siz tanlagan yo‘nalish bo‘yicha hozircha haydovchi topilmadi. Haydovchi kelganda sizga xabar yuboramiz", reply_markup=post_route_menu_passenger())
            return AFTER_ROUTE_MENU
        lines = []
        for m in matches:
            match_user = get_user(m[0])
            if match_user:
                match_trip = get_user_trip(m[0])
                if match_trip:
                    lines.append(format_match_info(match_user, match_trip, is_driver=True))
        if not lines:
            await update.message.reply_text("Kechirasiz, mos haydovchilar topilmadi.", reply_markup=post_route_menu_passenger())
            return AFTER_ROUTE_MENU
        await update.message.reply_text("\n\n".join(lines), reply_markup=post_route_menu_passenger())
    except Exception as e:
        await update.message.reply_text(f"Haydovchilarni ko‘rishda xato: {e}. Iltimos, qaytadan urinib ko‘ring.", reply_markup=post_route_menu_passenger())
        return AFTER_ROUTE_MENU

# ------------------ CHANGE SEATS (driver) ------------------
async def change_seats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Tanlang:", reply_markup=post_route_menu_driver())
        return AFTER_ROUTE_MENU
    if txt == BTN_POST:
        context.user_data['seats'] = "post"
        try:
            update_seats(update.effective_user.id, "post")
            await update.message.reply_text("Pochta tanlandi.", reply_markup=post_route_menu_driver())
            return AFTER_ROUTE_MENU
        except Exception as e:
            await update.message.reply_text(f"O‘rinlarni yangilashda xato: {e}. Iltimos, qaytadan urinib ko‘ring.", reply_markup=post_route_menu_driver())
            return AFTER_ROUTE_MENU
    if txt not in SEATS_BUTTONS:
        await update.message.reply_text("1 dan 6 gacha son tanlang yoki Pochta tugmasini bosing:", reply_markup=seats_keyboard())
        return CHANGE_SEATS_STATE
    seats = txt
    try:
        update_seats(update.effective_user.id, seats)
        await update.message.reply_text("Bo‘sh o‘rinlar soni yangilandi.", reply_markup=post_route_menu_driver())
        return AFTER_ROUTE_MENU
    except Exception as e:
        await update.message.reply_text(f"O‘rinlarni yangilashda xato: {e}. Iltimos, qaytadan urinib ko‘ring.", reply_markup=post_route_menu_driver())
        return AFTER_ROUTE_MENU

# ------------------ HELP / ADMIN ------------------
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom. Men SafarTaxi robotman.\n Savol yoki taklifingizni yozing, operatorlarimiz tez orada siz bilan bog‘lanadi:", reply_markup=back_keyboard())
    return HELP_MESSAGE

async def handle_help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    user_id = update.effective_user.id
    if txt == BTN_BACK:
        if user_id in ADMIN_IDS:
            await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
            return ADMIN_MENU
        user = get_user(user_id)
        if user:
            await update.message.reply_text("Profil menyusi:", reply_markup=show_main_menu_by_role(user['role']))
            return ConversationHandler.END
        return await start(update, context)
    username = update.effective_user.username or "Anonim"
    if not ADMIN_IDS:
        await update.message.reply_text("Adminlar topilmadi. Iltimos, .env faylida ADMINS=... qo‘shing.")
        return ConversationHandler.END
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Foydalanuvchi @{username} (ID: {user_id}) dan xabar:\n{txt}\nJavob berish uchun: /reply {user_id} <xabar>",
                disable_notification=True
            )
        except Exception as e:
            print(f"Xato yordam xabarini yuborishda (admin {admin_id}): {e}")
            await update.message.reply_text(f"Xabarni adminlarga yuborishda xato: {e}. Iltimos, qaytadan urinib ko‘ring.")
            return ConversationHandler.END
    await update.message.reply_text("Xabaringiz qabul qilindi. Operatorlarimiz tez orada siz bilan bog‘lanadi")
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"Admin panel accessed by user_id: {user_id}, is_admin: {user_id in ADMIN_IDS}")  # Debug
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Sizda admin ruxsati yo‘q.")
        return ConversationHandler.END
    await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
    return ADMIN_MENU

async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    print(f"Reply command from user_id: {user_id}, is_admin: {user_id in ADMIN_IDS}")  # Debug
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Sizda admin ruxsati yo‘q.")
        return ConversationHandler.END
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Iltimos, to‘g‘ri formatda kiriting: /reply <user_id> <xabar>\nMasalan: /reply 123456789 Salom, muammoingiz hal qilindi.",
            reply_markup=admin_menu_keyboard()
        )
        return ConversationHandler.END
    try:
        target_user_id = int(args[0])
        reply_text = " ".join(args[1:])
        user = get_user(target_user_id)
        if not user:
            await update.message.reply_text(f"Foydalanuvchi ID {target_user_id} topilmadi.", reply_markup=admin_menu_keyboard())
            return ConversationHandler.END
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"Operator 2:\n {reply_text}",
                disable_notification=True
            )
            await update.message.reply_text(f"Xabar {target_user_id} foydalanuvchiga yuborildi.", reply_markup=admin_menu_keyboard())
        except Exception as e:
            await update.message.reply_text(
                f"Foydalanuvchiga xabar yuborishda xato: {e}. Ehtimol, foydalanuvchi botni bloklagan yoki chat faol emas.",
                reply_markup=admin_menu_keyboard()
            )
    except ValueError:
        await update.message.reply_text(
            "Xato: user_id raqam bo‘lishi kerak. To‘g‘ri format: /reply <user_id> <xabar>",
            reply_markup=admin_menu_keyboard()
        )
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}. Iltimos, to‘g‘ri formatda kiriting.", reply_markup=admin_menu_keyboard())
    return ConversationHandler.END

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    user_id = update.effective_user.id
    print(f"Admin menu input: {txt}, user_id: {user_id}")  # Debug uchun tugma matnini ko‘rish
    if txt == BTN_BACK:
        user = get_user(user_id)
        if user:
            await update.message.reply_text("Profil menyusi:", reply_markup=show_main_menu_by_role(user['role']))
            return ConversationHandler.END
        return await start(update, context)
    try:
        if txt == BTN_ADMIN_STATS:
            s = get_stats()
            drivers_count, passengers_count = s if s else (0, 0)
            await update.message.reply_text(
                f"Statistika:\nHaydovchilar: {drivers_count}\nYo‘lovchilar: {passengers_count}",
                reply_markup=admin_menu_keyboard()
            )
        elif txt == BTN_ADMIN_DRIVERS:
            ads = get_all_drivers() or []
            drivers_text = "\n".join([f"{d[1]} - {d[2]}" for d in ads]) if ads else "Yo‘q"
            await update.message.reply_text(f"Haydovchilar:\n{drivers_text}", reply_markup=admin_menu_keyboard())
        elif txt == BTN_ADMIN_PASSENGERS:
            aps = get_all_passengers() or []
            passengers_text = "\n".join([f"{p[1]} - {p[2]}" for p in aps]) if aps else "Yo‘q"
            await update.message.reply_text(f"Yo‘lovchilar:\n{passengers_text}", reply_markup=admin_menu_keyboard())
        elif txt == BTN_ADMIN_REPLY:
            await update.message.reply_text(
                "Foydalanuvchiga xabar yuborish uchun format: <user_id> <xabar>\nMasalan: 123456789 Salom, muammoingiz hal qilindi.",
                reply_markup=back_keyboard()
            )
            return ADMIN_REPLY
        else:
            await update.message.reply_text("Iltimos, menyudan variant tanlang:", reply_markup=admin_menu_keyboard())
    except Exception as e:
        print(f"Admin menu error: {e}")  # Debug uchun xato loglari
        await update.message.reply_text(f"Xato yuz berdi: {e}. Iltimos, menyudan variant tanlang:", reply_markup=admin_menu_keyboard())
    return ADMIN_MENU

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import get_driver_count, get_passenger_count
    driver_count = get_driver_count()
    passenger_count = get_passenger_count()
    await update.message.reply_text(
        f"Statistika:\n"
        f"- Haydovchilar soni: {driver_count}\n"
        f"- Yo'lovchilar soni: {passenger_count}"
    )
    return ADMIN_MENU

async def admin_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database import get_all_drivers
    drivers = get_all_drivers()
    if not drivers:
        await update.message.reply_text("Hech qanday haydovchi topilmadi!")
        return ADMIN_MENU
    message = "Haydovchilar ro‘yxati:\n"
    for i, d in enumerate(drivers, 1):
        message += f"{i}. ({d['user_id']}, {d['full_name']}, {d['phone']}, {d.get('car_model', 'N/A')}, {d.get('car_color', 'N/A')}, {d.get('car_number', 'N/A')}),\n"
    await update.message.reply_text(message.rstrip(','))
    return ADMIN_MENU

async def admin_passengers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database import get_all_passengers
    passengers = get_all_passengers()
    if not passengers:
        await update.message.reply_text("Hech qanday yo‘lovchi topilmadi!")
        return ADMIN_MENU
    message = "Yo‘lovchilar ro‘yxati:\n"
    for i, p in enumerate(passengers, 1):
        message += f"{i}. ({p['user_id']}, {p['full_name']}, {p['phone']}),\n"
    await update.message.reply_text(message.rstrip(','))
    return ADMIN_MENU

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    try:
        parts = txt.split(" ", 1)
        if len(parts) < 2:
            await update.message.reply_text(
                "Iltimos, to‘g‘ri formatda kiriting: <user_id> <xabar>\nMasalan: 123456789 Salom, muammoingiz hal qilindi.",
                reply_markup=back_keyboard()
            )
            return ADMIN_REPLY
        target_user_id = int(parts[0])
        reply_text = parts[1]
        user = get_user(target_user_id)
        if not user:
            await update.message.reply_text(f"Foydalanuvchi ID {target_user_id} topilmadi. Iltimos, to‘g‘ri ID kiriting.", reply_markup=admin_menu_keyboard())
            return ADMIN_MENU
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"Admin javobi: {reply_text}",
                disable_notification=True
            )
            await update.message.reply_text(f"Xabar {target_user_id} foydalanuvchiga yuborildi.", reply_markup=admin_menu_keyboard())
            return ADMIN_MENU
        except Exception as e:
            await update.message.reply_text(
                f"Foydalanuvchiga xabar yuborishda xato: {e}. Ehtimol, foydalanuvchi botni bloklagan yoki chat faol emas.",
                reply_markup=admin_menu_keyboard()
            )
            return ADMIN_MENU
    except ValueError:
        await update.message.reply_text(
            "Xato: user_id raqam bo‘lishi kerak. To‘g‘ri format: <user_id> <xabar>",
            reply_markup=back_keyboard()
        )
        return ADMIN_REPLY
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}. Iltimos, to‘g‘ri formatda kiriting.", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU

async def send_to_all_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Sizda huquq yo‘q!")
        return ADMIN_MENU
    await update.message.reply_text("Xabar matnini kiriting:")
    return "SEND_TO_ALL_GROUPS"

async def handle_send_to_all_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text
    from database import get_all_users
    users = get_all_users()
    if not users:
        await update.message.reply_text("Hech qanday foydalanuvchi topilmadi!")
        return ADMIN_MENU
    success_count = 0
    for user in users:
        name = user.get('full_name', 'Noma’lum')
        personalized_message = f"Salom {name}! {message_text}"
        try:
            await context.bot.send_message(chat_id=user['user_id'], text=personalized_message)
            success_count += 1
        except Exception as e:
            print(f"Xabar yuborishda xatolik: {e}")
    await update.message.reply_text(f"Xabar {success_count} ta foydalanuvchiga yuborildi!")
    return ADMIN_MENU

async def send_to_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Sizda huquq yo‘q!")
        return ADMIN_MENU
    await update.message.reply_text("Xabar matnini kiriting:")
    return "SEND_TO_DRIVERS"

async def handle_send_to_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text
    from database import get_all_drivers
    drivers = get_all_drivers()
    if not drivers:
        await update.message.reply_text("Hech qanday haydovchi topilmadi!")
        return ADMIN_MENU
    success_count = 0
    for driver in drivers:
        name = driver.get('full_name', 'Noma’lum')
        personalized_message = f"Salom {name}! {message_text}"
        try:
            await context.bot.send_message(chat_id=driver['user_id'], text=personalized_message)
            success_count += 1
        except Exception as e:
            print(f"Xabar yuborishda xatolik: {e}")
    await update.message.reply_text(f"Xabar {success_count} ta haydovchiga yuborildi!")
    return ADMIN_MENU

async def send_to_passengers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Sizda huquq yo‘q!")
        return ADMIN_MENU
    await update.message.reply_text("Xabar matnini kiriting:")
    return "SEND_TO_PASSENGERS"

async def handle_send_to_passengers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_text = update.message.text
    from database import get_all_passengers
    passengers = get_all_passengers()
    if not passengers:
        await update.message.reply_text("Hech qanday yo‘lovchi topilmadi!")
        return ADMIN_MENU
    success_count = 0
    for passenger in passengers:
        name = passenger.get('full_name', 'Noma’lum')
        personalized_message = f"Salom {name}! {message_text}"
        try:
            await context.bot.send_message(chat_id=passenger['user_id'], text=personalized_message)
            success_count += 1
        except Exception as e:
            print(f"Xabar yuborishda xatolik: {e}")
    await update.message.reply_text(f"Xabar {success_count} ta yo‘lovchiga yuborildi!")
    return ADMIN_MENU

async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) not in ADMIN_IDS:
        await update.message.reply_text("Sizda admin huquqi yo‘q!")
        return ConversationHandler.END
    
    if not context.args:
        await update.message.reply_text("Iltimos, user_id ni kiriting: /delete_user <user_id>")
        return ADMIN_MENU
    
    try:
        target_user_id = int(context.args[0])
        from database import delete_user
        deleted_count = delete_user(target_user_id)
        if deleted_count > 0:
            await update.message.reply_text(f"User ID {target_user_id} muvaffaqiyatli o‘chirildi.")
        else:
            await update.message.reply_text(f"User ID {target_user_id} topilmadi.")
        return ADMIN_MENU
    except ValueError:
        await update.message.reply_text("Noto‘g‘ri user_id format!")
        return ADMIN_MENU        

async def delete_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("O‘chirish uchun user_id ni kiriting:")
    return "DELETE_USER_INPUT"

async def delete_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Admin foydalanuvchini o'chirish uchun ID ni qabul qiladi."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Sizda bu komandani ishlatish huquqi yo‘q!")
        return ConversationHandler.END

    text = update.message.text.strip()
    if text == BTN_BACK:
        await update.message.reply_text("Orqaga qaytildi.", reply_markup=main_menu_keyboard())
        return ADMIN_MENU

    try:
        user_id = int(text)
    except ValueError:
        await update.message.reply_text("Iltimos, faqat foydalanuvchi ID sini raqam sifatida kiriting!")
        return "DELETE_USER_INPUT"

    # Foydalanuvchini o'chirish logikasi
    success = delete_user(user_id)
    if success:
        await update.message.reply_text(f"Foydalanuvchi ID {user_id} muvaffaqiyatli o'chirildi!")
    else:
        await update.message.reply_text(f"Foydalanuvchi ID {user_id} topilmadi yoki o'chirishda xatolik yuz berdi!")
    return ADMIN_MENU  

# ------------------ ADMIN HANDLERS ------------------
async def admin_advert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Reklama joylash uchun matn yoki rasm so'rash."""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Sizda admin huquqlari yo‘q!")
        return ConversationHandler.END
    await update.message.reply_text(
        "Reklama matnini kiriting (rasm yuborish mumkin, Markdown qo'llab-quvvatlanadi):",
        reply_markup=back_keyboard()
    )
    return ADVERT_MESSAGE

async def handle_advert_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Reklama xabarini barcha foydalanuvchilarga yuborish."""
    txt = update.message.text if update.message.text else ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    if txt == BTN_BACK:
        await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Batafsil", url="https://t.me/your_channel_or_link")]
    ])
    user_ids = get_all_users_chat_ids()
    success = 0
    for uid in user_ids:
        try:
            if photo:
                await context.bot.send_photo(
                    chat_id=uid,
                    photo=photo,
                    caption=txt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard
                )
            else:
                await context.bot.send_message(
                    chat_id=uid,
                    text=txt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard
                )
            success += 1
        except Exception as e:
            logger.error(f"Reklama yuborishda xato (user {uid}): {e}")
    await update.message.reply_text(
        f"Reklama {success} ta foydalanuvchiga yuborildi.",
        reply_markup=admin_menu_keyboard()
    )
    return ADMIN_MENU

# ------------------ FLASK WEBHOOK ------------------
@flask_app.route("/payment_callback_click", methods=["POST"])
def payment_callback_click():
    """Click to'lov tasdiqlash webhook."""
    data = request.get_json()
    if not data or data.get('status') != 'success':
        logger.warning("Click to‘lov tasdiqlanmadi")
        return jsonify({"status": "error"}), 400
    transaction_param = data.get('transaction_param')
    parts = transaction_param.split('_')
    user_id = int(parts[1])
    duration_str = '_'.join(parts[2:])
    durations = {
        "1_kunlik_(3000_so'm)": 1,
        "10_kunlik_(20000_so'm)": 10,
        "1_oylik_(40000_so'm)": 30,
        "6_oylik_(180000_so'm)": 180,
        "1_yillik_(320000_so'm)": 365
    }
    days = durations.get(duration_str, 0)
    if days:
        update_subscription(user_id, days)
        logger.info(f"Click to‘lov tasdiqlandi: user_id={user_id}, days={days}")
        return jsonify({"status": "ok"}), 200
    logger.warning(f"Noto‘g‘ri obuna turi: {duration_str}")
    return jsonify({"status": "error"}), 400

@flask_app.route("/payment_callback_payme", methods=["POST"])
def payment_callback_payme():
    """Payme to'lov tasdiqlash webhook."""
    data = request.get_json()
    if not data or data.get("method") != "CheckTransaction":
        logger.error("Noto‘g‘ri Payme webhook so‘rovi")
        return jsonify({"error": "Invalid request"}), 400
    if data["result"].get("state") == 2:
        order_id = data["params"].get("account", {}).get("order_id")
        parts = order_id.split('_')
        user_id = int(parts[1])
        duration_str = '_'.join(parts[2:])
        durations = {
            "1_kunlik_(3000_so'm)": 1,
            "10_kunlik_(20000_so'm)": 10,
            "1_oylik_(40000_so'm)": 30,
            "6_oylik_(180000_so'm)": 180,
            "1_yillik_(320000_so'm)": 365
        }
        days = durations.get(duration_str, 0)
        if days:
            update_subscription(user_id, days)
            logger.info(f"Payme to‘lov tasdiqlandi: user_id={user_id}, days={days}")
            return jsonify({"result": {"state": 2}}), 200
    logger.warning("Payme to‘lov tasdiqlanmadi")
    return jsonify({"error": "Transaction not successful"}), 400

async def check_expired_trips():
    from database import delete_expired_trips
    deleted_count = delete_expired_trips()
    if deleted_count > 0:
        print(f"{deleted_count} ta eskirgan trip o‘chirildi.")

def run_schedule():
    schedule.every(24).hours.do(lambda: asyncio.run(check_expired_trips()))
    while True:
        schedule.run_pending()
        time.sleep(60)    

async def set_webhook():
    await app.bot.set_webhook(url=WEBHOOK_URL + "/webhook")
    print("Webhook sozlandi:", WEBHOOK_URL + "/webhook")

route_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{BTN_EDIT_PROFILE}$"), edit_profile),
            MessageHandler(filters.Regex(f"^{BTN_CHOOSE_ROUTE}$"), choose_route),
            MessageHandler(
                filters.Regex(f"^{BTN_SEE_PASSENGERS}$|^{BTN_CHANGE_SEATS}$|^{BTN_GO}$|^{BTN_SEE_DRIVERS}$|^{BTN_SEND_GEO}$|^{BTN_BACK}$"),
                after_route_router
            ),
            MessageHandler(filters.Regex(f"^{BTN_HELP}$"), help_cmd),
            CommandHandler("admin", admin_panel),
            CommandHandler("delete_user", delete_user_command),
        ],
        states={
            CHOOSE_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_PHONE: [
                MessageHandler(filters.CONTACT, register_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_phone),
            ],
            REGISTER_CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_model)],
            REGISTER_CAR_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_color)],
            REGISTER_CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_number)],
            SUBSCRIPTION_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subscription)],
            FROM_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_region)],
            FROM_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_district)],
            FROM_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, from_area)],
            TO_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, to_region)],
            TO_DISTRICT: [MessageHandler(filters.TEXT & ~filters.COMMAND, to_district)],
            ENTER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_price)],
            CHOOSE_SEATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_seats)],
            WHEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, when_choice)],
            WHEN_PLAN_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, when_plan_date)],
            WHEN_PLAN_HOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, when_plan_hour)],
            AFTER_ROUTE_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, after_route_router)],
            CHANGE_SEATS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, change_seats)],
            HELP_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_message)],
            ADMIN_MENU: [
                MessageHandler(filters.Regex(f"^{BTN_ADMIN_STATS}$"), admin_stats),
                MessageHandler(filters.Regex(f"^{BTN_ADMIN_DRIVERS}$"), admin_drivers),
                MessageHandler(filters.Regex(f"^{BTN_ADMIN_PASSENGERS}$"), admin_passengers),
                MessageHandler(filters.Regex(f"^{BTN_ADMIN_REPLY}$"), admin_reply),
                MessageHandler(filters.Regex(f"^{SEND_TO_ALL_GROUPS}$"), send_to_all_groups),
                MessageHandler(filters.Regex(f"^{SEND_TO_DRIVERS}$"), send_to_drivers),
                MessageHandler(filters.Regex(f"^{SEND_TO_PASSENGERS}$"), send_to_passengers),
                MessageHandler(filters.Regex(f"^{BTN_ADMIN_ADVERT}$"), admin_advert),
                MessageHandler(filters.Regex(f"^{BTN_BACK}$"), start),
                MessageHandler(filters.Regex(f"^{BTN_DELETE_USER_PROMPT}$"), delete_user_prompt)
            ],
            "ADMIN_REPLY": [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply)],
            ADVERT_MESSAGE: [MessageHandler(filters.TEXT | filters.PHOTO, handle_advert_message)],
            "SEND_TO_ALL_GROUPS": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_send_to_all_groups)],
            "SEND_TO_DRIVERS": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_send_to_drivers)],
            "SEND_TO_PASSENGERS": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_send_to_passengers)],
            "DELETE_USER_INPUT": [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_user_input)],
            SUBSCRIPTION_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subscription)],
            PAYMENT_METHOD_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_method)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{BTN_BACK}$"), after_route_router),
            MessageHandler(filters.Regex(f"^{BTN_BACK_TO_MENU}$"), start),
        ],
        per_chat=True,
    )

start_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_PHONE: [
                MessageHandler(filters.CONTACT, register_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, register_phone),
        ],
            REGISTER_CAR_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_model)],
            REGISTER_CAR_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_color)],
            REGISTER_CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_car_number)],
        },
        fallbacks=[MessageHandler(filters.Regex(f"^{BTN_BACK_TO_MENU}$"), start)],
        per_chat=True,
    )

async def request_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Geolokatsiya so'rash."""
    user = get_user(update.effective_user.id)
    if not user or user.get('role') != 'passenger':
        await update.message.reply_text("Siz yo‘lovchi emassiz!")
        return ConversationHandler.END
    trip = get_user_trip(update.effective_user.id)
    if not trip:
        await update.message.reply_text("Iltimos, avval yo‘nalishni belgilang!")
        return ConversationHandler.END
    drivers = get_matching_drivers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
    if not drivers:
        await update.message.reply_text("Bu yo‘nalishda haydovchi topilmadi!")
        return ConversationHandler.END
    keyboard = [[KeyboardButton(driver.get('full_name', 'Noma’lum haydovchi'))] for driver in drivers] + [[KeyboardButton(BTN_BACK)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Mos haydovchilarni tanlang:", reply_markup=reply_markup)
    context.user_data['drivers'] = drivers
    return "SELECT_DRIVER"

async def select_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Haydovchini tanlash."""
    selected_name = update.message.text
    drivers = context.user_data.get('drivers', [])
    driver = next((d for d in drivers if d.get('full_name') == selected_name), None)
    if not driver or update.message.text == BTN_BACK:
        await update.message.reply_text("Orqaga qaytildi.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    context.user_data['selected_driver'] = driver
    keyboard = [[KeyboardButton("Geolokatsiya yuborish", request_location=True)], [KeyboardButton(BTN_BACK)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(f"Tanlangan haydovchi: {driver.get('full_name', 'Noma’lum')}. Geolokatsiyangizni yuboring:", reply_markup=reply_markup)
    return "LOCATION_STATE"

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Geolokatsiyani qayta ishlash."""
    if update.message.location:
        latitude = update.message.location.latitude
        longitude = update.message.location.longitude
        driver = context.user_data.get('selected_driver')
        if driver and 'user_id' in driver:
            await context.bot.send_message(
                chat_id=driver['user_id'],
                text=f"Yo‘lovchi geolokatsiyasi: latitude={latitude}, longitude={longitude}. Xarita: https://maps.google.com/?q={latitude},{longitude}"
            )
            logger.info(f"Geolokatsiya yuborildi: driver_id={driver['user_id']}")
        await update.message.reply_text("Geolokatsiya tanlangan haydovchiga yuborildi!", reply_markup=main_menu_passenger())
    return ConversationHandler.END

location_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex(f"^{BTN_SEND_GEO}$"), request_location)],
    states={
        "SELECT_DRIVER": [MessageHandler(filters.TEXT & ~filters.COMMAND, select_driver)],
        "LOCATION_STATE": [MessageHandler(filters.LOCATION, handle_location)],
    },
    fallbacks=[MessageHandler(filters.Regex(f"^{BTN_BACK}$"), start)],
    per_chat=True,
)

# ------------------ MAIN ------------------
def main():
    # Ma'lumotlar bazasini ishga tushirish
    init_db()
    logger.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushdi")

    # Ilova obyekti
    app = Application.builder().token(BOT_TOKEN).build()
    logger.info("Application obyekti yaratildi")

    # Handler larni qo'shish
    app.add_handler(route_conv)
    app.add_handler(start_conv)
    app.add_handler(location_conv)
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(CommandHandler("reply", reply_command))
    app.add_handler(CommandHandler("send_all", send_to_all_groups))
    app.add_handler(CommandHandler("send_drivers", send_to_drivers))
    app.add_handler(CommandHandler("send_passengers", send_to_passengers))
    app.add_handler(CommandHandler("payment_callback_click", payment_callback_click))
    app.add_handler(CommandHandler("payment_callback_payme", payment_callback_payme))
    

    # Webhook ni sozlash
    logger.info("Bot webhook rejimida ishga tushdi...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL + "/webhook"
    )

if __name__ == "__main__":
    main()