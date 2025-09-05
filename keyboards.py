from telegram import KeyboardButton, ReplyKeyboardMarkup

def role_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Haydovchi"), KeyboardButton("Yo‘lovchi")],
        [KeyboardButton("Orqaga")]
    ], resize_keyboard=True)

def phone_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Telefon raqamni yuborish", request_contact=True)],
        [KeyboardButton("Orqaga")]
    ], resize_keyboard=True)

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton(BTN_DRIVER), KeyboardButton(BTN_PASSENGER)],
        [KeyboardButton(BTN_CHOOSE_ROUTE), KeyboardButton(BTN_EDIT_PROFILE)],
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def main_menu_driver():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Yo‘nalish tanlash"), KeyboardButton("Profilni tahrirlash")],
        [KeyboardButton("Yordam")]
    ], resize_keyboard=True)

def main_menu_passenger():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Yo‘nalish tanlash"), KeyboardButton("Profilni tahrirlash")],
        [KeyboardButton("Yordam")]
    ], resize_keyboard=True)

def post_route_menu_driver():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Yo‘lovchilarni ko‘rish"), KeyboardButton("Bo‘sh joylar soni")],
        [KeyboardButton("Ketdik"), KeyboardButton("Orqaga")]
    ], resize_keyboard=True)

def post_route_menu_passenger():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Haydovchilarni ko‘rish"), KeyboardButton("Geolokatsiya yuborish")],
        [KeyboardButton("Ketdik"), KeyboardButton("Orqaga")]
    ], resize_keyboard=True)

def regions_keyboard():
    from regions import regions
    buttons = [[KeyboardButton(r)] for r in regions.keys()]
    buttons.append([KeyboardButton("Orqaga")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def districts_keyboard(region):
    from regions import regions
    buttons = [[KeyboardButton(d)] for d in regions.get(region, [])]
    buttons.append([KeyboardButton("Orqaga")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def seats_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("1"), KeyboardButton("2"), KeyboardButton("3")],
        [KeyboardButton("4"), KeyboardButton("5"), KeyboardButton("6")],
        [KeyboardButton("Pochta")],
        [KeyboardButton("Orqaga")]
    ], resize_keyboard=True)

def when_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Hozir"), KeyboardButton("Rejalashtirish")],
        [KeyboardButton("Orqaga")]
    ], resize_keyboard=True)

def date_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Bugun"), KeyboardButton("Ertaga")],
        [KeyboardButton("Boshqa sana"), KeyboardButton("Orqaga")]
    ], resize_keyboard=True)

def hour_keyboard():
    buttons = [[KeyboardButton(f"{i:02d}:00") for i in range(j, j+4)] for j in range(0, 24, 4)]
    buttons.append([KeyboardButton("Orqaga")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def admin_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Foydalanuvchilar soni"), KeyboardButton("Haydovchilar ma'lumotlari")],
        [KeyboardButton("Yo‘lovchilar ma'lumotlari"), KeyboardButton("Xabar yuborish")],
        [KeyboardButton("Foydalanuvchini o‘chirish"), KeyboardButton("Orqaga")]
    ], resize_keyboard=True)