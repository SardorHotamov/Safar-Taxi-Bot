import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from database import init_db, get_user, save_user, get_user_trip, save_trip, update_seats, delete_trip, get_matching_drivers, get_matching_passengers, get_stats, get_all_drivers, get_all_passengers
from keyboards import role_keyboard, main_menu_driver, main_menu_passenger, regions_keyboard, districts_keyboard, seats_keyboard, when_keyboard, phone_keyboard, post_route_menu_driver, post_route_menu_passenger, date_keyboard, hour_keyboard, admin_menu_keyboard
from utils import is_valid_date, format_date

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = set(int(id) for id in os.getenv("ADMINS", "").split(",") if id)

BTN_DRIVER = "Haydovchi"
BTN_PASSENGER = "Yo‘lovchi"
BTN_CHOOSE_ROUTE = "Yo‘nalish tanlash"
BTN_EDIT_PROFILE = "Profilni tahrirlash"
BTN_HELP = "Yordam"

BTN_SEE_PASSENGERS = "Yo‘lovchilarni ko‘rish"
BTN_CHANGE_SEATS = "Bo‘sh joylar soni"
BTN_GO = "Ketdik"

BTN_SEE_DRIVERS = "Haydovchilarni ko‘rish"
BTN_SEND_GEO = "Geolokatsiya yuborish"

BTN_BACK = "Orqaga"
BTN_BACK_TO_MENU = "Asosiy menyu"
BTN_NOW = "Hozir"
BTN_PLAN = "Rejalashtirish"
BTN_TODAY = "Bugun"
BTN_TOMORROW = "Ertaga"
BTN_OTHER_DATE = "Boshqa sana"
BTN_POST = "Pochta"

BTN_ADMIN_STATS = "Foydalanuvchilar soni"
BTN_ADMIN_DRIVERS = "Haydovchilar ma'lumotlari"
BTN_ADMIN_PASSENGERS = "Yo‘lovchilar ma'lumotlari"
BTN_ADMIN_REPLY = "Xabar yuborish"

SEATS_BUTTONS = ["1", "2", "3", "4", "5", "6"]

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
) = range(21)

def back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton(BTN_BACK)]], resize_keyboard=True)

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
            f"Qayerdan: {trip['from_region']}, {trip['from_district']}{mahalla_str}\n"
            f"Qayerga: {trip['to_region']}, {trip['to_district']}\n"
            f"Qachon: {when}\n"
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
                f"Qayerdan: {from_region}, {from_district}{mahalla_str}\n"
                f"Qayerga: {to_region}, {to_district}\n"
                f"Qachon: {when}")
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

# ------------------ START / REGISTRATION ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    user_id = update.effective_user.id
    print(f"Start command from user_id: {user_id}, is_admin: {user_id in ADMIN_IDS}")  # Debug
    if user_id in ADMIN_IDS:
        await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    user = get_user(user_id)
    if user:
        await update.message.reply_text("Profil menyusi:", reply_markup=show_main_menu_by_role(user['role']))
        return ConversationHandler.END

    text = (
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
        "  • Mosini tanlab, telefon orqali bog‘lanasiz\n\n"
    )
    await update.message.reply_text(text + "Rolni tanlang:", reply_markup=role_keyboard())
    return CHOOSE_ROLE

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
        await update.message.reply_text("Rolni tanlang:", reply_markup=role_keyboard())
        return CHOOSE_ROLE
    if len(txt) < 3:
        await update.message.reply_text("Ism va familiya kamida 3 harfdan iborat bo‘lsin:", reply_markup=back_keyboard())
        return REGISTER_NAME
    context.user_data['full_name'] = txt
    await update.message.reply_text("Telefon raqamingizni yuboring (+998...):", reply_markup=phone_keyboard())
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
        await update.message.reply_text("To‘g‘ri telefon raqamini kiriting (+998...):", reply_markup=phone_keyboard())
        return REGISTER_PHONE
    context.user_data['phone'] = normalize_phone(p)
    role = context.user_data.get('role')
    if role == "driver":
        await update.message.reply_text("Avtomobil modelingizni kiriting:", reply_markup=back_keyboard())
        return REGISTER_CAR_MODEL
    else:
        save_user(update.effective_user.id, role, context.user_data['full_name'], context.user_data['phone'])
        await update.message.reply_text("Ro‘yxatdan o‘tdingiz! Endi yo‘nalish tanlashingiz mumkin.", reply_markup=main_menu_passenger())
        return ConversationHandler.END

async def register_car_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
        return REGISTER_PHONE
    context.user_data['car_model'] = txt
    await update.message.reply_text("Avtomobil rangingizni kiriting:", reply_markup=back_keyboard())
    return REGISTER_CAR_COLOR

async def register_car_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Avtomobil modelingizni kiriting:", reply_markup=back_keyboard())
        return REGISTER_CAR_MODEL
    context.user_data['car_color'] = txt
    await update.message.reply_text("Avtomobil raqamingizni kiriting (masalan, 01A123BC):", reply_markup=back_keyboard())
    return REGISTER_CAR_NUMBER

async def register_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Avtomobil rangingizni kiriting:", reply_markup=back_keyboard())
        return REGISTER_CAR_COLOR
    if not is_valid_license(txt):
        await update.message.reply_text("Avtomobil raqami 7—10 belgidagi bo‘lsin:", reply_markup=back_keyboard())
        return REGISTER_CAR_NUMBER
    context.user_data['car_number'] = txt.upper()
    save_user(update.effective_user.id, context.user_data['role'], context.user_data['full_name'], context.user_data['phone'],
              context.user_data['car_model'], context.user_data['car_color'], context.user_data['car_number'])
    await update.message.reply_text("Ro‘yxatdan o‘tdingiz! Endi yo‘nalish tanlashingiz mumkin.", reply_markup=main_menu_driver())
    return ConversationHandler.END

# ------------------ EDIT PROFILE ------------------
async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Profilni tahrirlash: Rolni tanlang:", reply_markup=role_keyboard())
    return CHOOSE_ROLE

# ------------------ CHOOSE ROUTE ------------------
async def choose_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Iltimos, avval ro‘yxatdan o‘ting.", reply_markup=role_keyboard())
        return CHOOSE_ROLE
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
    await update.message.reply_text("Mahalla yoki aniq manzilni kiriting (ixtiyoriy, o‘tkazib yuborish uchun Enter bosing):", reply_markup=back_keyboard())
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
        await update.message.reply_text("Narxni kiriting (so‘mda, ixtiyoriy, o‘tkazib yuborish uchun Enter bosing):", reply_markup=back_keyboard())
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
    await update.message.reply_text("Bo‘sh o‘rinlar sonini yoki pochta jo‘natishni tanlang:", reply_markup=seats_keyboard())
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
        await update.message.reply_text("Hozir yoki Rejalashtirish tanlang:", reply_markup=when_keyboard())
        return WHEN
    context.user_data['when_mode'] = 'now' if txt == BTN_NOW else 'plan'
    if txt == BTN_NOW:
        await save_and_notify(update, context)
        return AFTER_ROUTE_MENU
    else:
        await update.message.reply_text("Sanani tanlang:", reply_markup=date_keyboard())
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
    await update.message.reply_text("Endi quyidagilarni bajaring:", reply_markup=rm)
    # Notify matching users
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Foydalanuvchi ma'lumotlari topilmadi.")
        return ConversationHandler.END
    if role == "driver":
        matches = get_matching_passengers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
        for m in matches:
            match_id = m['user_id']
            match_user = get_user(match_id)
            match_trip = get_user_trip(match_id)
            if match_user and match_trip:
                await context.bot.send_message(
                    chat_id=match_id,
                    text=f"Yangi haydovchi qo'shildi:\n{format_match_info(user, trip, is_driver=True)}"
                )
    else:
        matches = get_matching_drivers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
        for m in matches:
            match_id = m['user_id']
            match_user = get_user(match_id)
            match_trip = get_user_trip(match_id)
            if match_user and match_trip:
                await context.bot.send_message(
                    chat_id=match_id,
                    text=f"Yangi yo'lovchi qo'shildi:\n{format_match_info(user, trip, is_driver=False)}"
                )

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
            await update.message.reply_text("Yangi bo‘sh o‘rinlar sonini yoki pochta jo‘natishni tanlang:", reply_markup=seats_keyboard())
            return CHANGE_SEATS_STATE
        elif txt == BTN_GO:
            delete_trip(user_id)
            await update.message.reply_text("Yo‘nalish yakunlandi.", reply_markup=main_menu_driver())
            return ConversationHandler.END
    else:
        if txt == BTN_SEE_DRIVERS:
            return await see_drivers(update, context)
        elif txt == BTN_SEND_GEO:
            await update.message.reply_text("Geolokatsiyangizni yuboring:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Geolokatsiya yuborish", request_location=True)]], resize_keyboard=True))
            return AFTER_ROUTE_MENU
        elif txt == BTN_GO:
            delete_trip(user_id)
            await update.message.reply_text("Yo‘nalish yakunlandi.", reply_markup=main_menu_passenger())
            return ConversationHandler.END
    await update.message.reply_text("Iltimos, quyidagi variantlardan birini tanlang:", reply_markup=post_route_menu_driver() if role == "driver" else post_route_menu_passenger())
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
            await update.message.reply_text("Kechirasiz, siz tanlagan yo‘nalish bo‘yicha hozircha yo‘lovchi topilmadi.", reply_markup=post_route_menu_driver())
            return AFTER_ROUTE_MENU
        lines = []
        for m in matches:
            match_user = get_user(m['user_id'])
            if match_user:
                lines.append(format_match_info(match_user, m, is_driver=False))
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
            await update.message.reply_text("Kechirasiz, siz tanlagan yo‘nalish bo‘yicha hozircha haydovchi topilmadi.", reply_markup=post_route_menu_passenger())
            return AFTER_ROUTE_MENU
        lines = []
        for m in matches:
            match_user = get_user(m['user_id'])
            if match_user:
                lines.append(format_match_info(match_user, m, is_driver=True))
        if not lines:
            await update.message.reply_text("Kechirasiz, mos haydovchilar topilmadi.", reply_markup=post_route_menu_passenger())
            return AFTER_ROUTE_MENU
        await update.message.reply_text("\n\n".join(lines), reply_markup=post_route_menu_passenger())
    except Exception as e:
        await update.message.reply_text(f"Haydovchilarni ko‘rishda xato: {e}. Iltimos, qaytadan urinib ko‘ring.", reply_markup=post_route_menu_passenger())
        return AFTER_ROUTE_MENU

# ------------------ HANDLE LOCATION ------------------
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    if not loc:
        await update.message.reply_text("Geolokatsiya yuborilmadi. Iltimos, qaytadan urinib ko‘ring.")
        return AFTER_ROUTE_MENU
    user_id = update.effective_user.id
    trip = get_user_trip(user_id)
    if not trip:
        await update.message.reply_text("Yo‘nalish topilmadi. Iltimos, yo‘nalish tanlang.")
        return await choose_route(update, context)
    try:
        drivers = get_matching_drivers(trip['from_region'], trip['from_district'], trip['to_region'], trip['to_district'])
        if not drivers:
            await update.message.reply_text("Hozircha mos haydovchi topilmadi.", reply_markup=post_route_menu_passenger())
            return AFTER_ROUTE_MENU
        for d in drivers[:1]:
            driver_id = d['user_id']
            await context.bot.send_location(chat_id=driver_id, latitude=loc.latitude, longitude=loc.longitude)
            await context.bot.send_message(chat_id=driver_id, text=f"Yo‘lovchining geolokatsiyasi (ID: {user_id})")
            await update.message.reply_text("Geolokatsiya tanlangan haydovchiga yuborildi.", reply_markup=post_route_menu_passenger())
            return AFTER_ROUTE_MENU
    except Exception as e:
        print(f"Xato geolokatsiya yuborishda (haydovchi {driver_id}): {e}")
        await update.message.reply_text(f"Geolokatsiyani yuborishda xato: {e}. Iltimos, qaytadan urinib ko‘ring.", reply_markup=post_route_menu_passenger())
    await update.message.reply_text("Geolokatsiyani yuborishda xatolik yuz berdi.", reply_markup=post_route_menu_passenger())
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
            await update.message.reply_text("Pochta jo‘natish tanlandi.", reply_markup=post_route_menu_driver())
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
    await update.message.reply_text("Savol yoki taklifingizni yozing (adminlarga yuboriladi):", reply_markup=back_keyboard())
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
                text=f"Foydalanuvchi @{username} (ID: {user_id}) dan xabar:\n{txt}\nJavob berish uchun: /reply {user_id}",
                disable_notification=True
            )
        except Exception as e:
            print(f"Xato yordam xabarini yuborishda (admin {admin_id}): {e}")
            await update.message.reply_text(f"Xabarni adminlarga yuborishda xato: {e}. Iltimos, qaytadan urinib ko‘ring.")
            return ConversationHandler.END
    await update.message.reply_text("Xabaringiz adminlarga yuborildi. Javobni kuting.")
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
    if len(args) < 1:
        await update.message.reply_text(
            "Iltimos, to‘g‘ri formatda kiriting: /reply <user_id>\nKeyin xabarni yozing yoki orqaga suring.",
            reply_markup=admin_menu_keyboard()
        )
        return ConversationHandler.END
    try:
        target_user_id = int(args[0])
        reply_text = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        user = get_user(target_user_id)
        if not user:
            await update.message.reply_text(f"Foydalanuvchi ID {target_user_id} topilmadi.", reply_markup=admin_menu_keyboard())
            return ConversationHandler.END
        message_text = update.message.text if update.message.text else ""
        full_reply = f"Admin javobi:\n{message_text}\n{reply_text}" if message_text and reply_text else f"Admin javobi:\n{message_text or reply_text}"
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=full_reply,
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
            "Xato: user_id raqam bo‘lishi kerak. To‘g‘ri format: /reply <user_id>",
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
    if txt == BTN_ADMIN_STATS:
        try:
            s = get_stats()
            drivers_count, passengers_count = s if s else (0, 0)
            await update.message.reply_text(
                f"Statistika:\nHaydovchilar: {drivers_count}\nYo‘lovchilar: {passengers_count}",
                reply_markup=admin_menu_keyboard()
            )
        except Exception as e:
            await update.message.reply_text(f"Statistikani olishda xato: {e}.", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    elif txt == BTN_ADMIN_DRIVERS:
        try:
            ads = get_all_drivers() or []
            drivers_text = "\n".join([f"{d[1]} - {d[2]}" for d in ads]) if ads else "Yo‘q"
            await update.message.reply_text(f"Haydovchilar:\n{drivers_text}", reply_markup=admin_menu_keyboard())
        except Exception as e:
            await update.message.reply_text(f"Haydovchilarni olishda xato: {e}.", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    elif txt == BTN_ADMIN_PASSENGERS:
        try:
            aps = get_all_passengers() or []
            passengers_text = "\n".join([f"{p[1]} - {p[2]}" for p in aps]) if aps else "Yo‘q"
            await update.message.reply_text(f"Yo‘lovchilar:\n{passengers_text}", reply_markup=admin_menu_keyboard())
        except Exception as e:
            await update.message.reply_text(f"Yo‘lovchilarni olishda xato: {e}.", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    elif txt == BTN_ADMIN_REPLY:
        await update.message.reply_text(
            "Foydalanuvchiga xabar yuborish uchun:\n/reply <user_id>\nKeyin xabarni yozing yoki orqaga suring.",
            reply_markup=back_keyboard()
        )
        return ADMIN_REPLY
    await update.message.reply_text("Iltimos, menyudan variant tanlang:", reply_markup=admin_menu_keyboard())
    return ADMIN_MENU

async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == BTN_BACK:
        await update.message.reply_text("Admin menyusi:", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU
    try:
        parts = txt.split(" ", 1)
        if len(parts) < 1:
            await update.message.reply_text(
                "Iltimos, to‘g‘ri formatda kiriting: /reply <user_id>\nKeyin xabarni yozing yoki orqaga suring.",
                reply_markup=back_keyboard()
            )
            return ADMIN_REPLY
        target_user_id = int(parts[0])
        reply_text = parts[1] if len(parts) > 1 else ""
        user = get_user(target_user_id)
        if not user:
            await update.message.reply_text(f"Foydalanuvchi ID {target_user_id} topilmadi. Iltimos, to‘g‘ri ID kiriting.", reply_markup=admin_menu_keyboard())
            return ADMIN_MENU
        message_text = update.message.text if update.message.text else ""
        full_reply = f"Admin javobi:\n{message_text}\n{reply_text}" if message_text and reply_text else f"Admin javobi:\n{message_text or reply_text}"
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=full_reply,
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
            "Xato: user_id raqam bo‘lishi kerak. To‘g‘ri format: /reply <user_id>",
            reply_markup=back_keyboard()
        )
        return ADMIN_REPLY
    except Exception as e:
        await update.message.reply_text(f"Xato: {e}. Iltimos, to‘g‘ri formatda kiriting.", reply_markup=admin_menu_keyboard())
        return ADMIN_MENU

# ------------------ MAIN ------------------
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. .env faylida BOT_TOKEN=... deb qo‘ying.")

    # Ma'lumotlar bazasini ishga tushirish
    init_db()

    app = Application.builder().token(BOT_TOKEN).pool_timeout(10).get_updates_pool_timeout(60).build()

    # Webhook sozlamalari
    port = int(os.getenv("PORT", 5000))  # Render'da PORT environment o'zgaruvchisi
    path = os.getenv("PATH", "webhook").replace("\\", "/").strip()  # Noto'g'ri qochishlarni tozalash
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_URL', 'localhost')}/{path}"  # Xavfsiz URL
    
    # Webhook'ni sozlash
    app.run_webhook(
       listen="0.0.0.0",  # Barcha ulanishlarni qabul qilish
       port=port,         # Port
       url_path=path,     # Tozalangan yo'l
       webhook_url=webhook_url  # Tashqi URL
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
    app.add_handler(start_conv)

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
            ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu)],
            ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{BTN_BACK}$"), after_route_router),
            MessageHandler(filters.Regex(f"^{BTN_BACK_TO_MENU}$"), start),
        ],
        per_chat=True,
    )
    app.add_handler(route_conv)

    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(CommandHandler("reply", reply_command))

    # app.run_polling() o'rniga webhook ishlatiladi, yuqorida sozlangan

if __name__ == "__main__":
    main()