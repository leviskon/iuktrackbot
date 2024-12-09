import time
import sqlite3
import base64
import hashlib
import qrcode
from io import BytesIO
from PIL import Image
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
import os

# Установка токена
API_TOKEN = "8127623558:AAEfPnFvcOrTkGqdvLheCdtMEB5Us5RFQb8"

# Создаем бота и диспетчер
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Кнопки
kb = ReplyKeyboardMarkup(resize_keyboard=True)
kb.add(KeyboardButton("Get ID"), KeyboardButton("Generate QR Code"))

# Подключение к базе данных
db_file = "university.db"

# Команда start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Добро пожаловать! Выберите действие:", reply_markup=kb)

# Обработка команды Get ID
@dp.message_handler(lambda message: message.text == "Get ID")
async def get_id(message: types.Message):
    telegram_id = message.from_user.id
    await message.reply(f"Ваш Telegram ID: {telegram_id}")

# Генерация QR-кода с меткой времени
@dp.message_handler(lambda message: message.text == "Generate QR Code")
async def generate_qr_code(message: types.Message):
    telegram_id = 1
    entry_time = int(time.time())  # Время входа в университет
    qr_code_path = f"qrcodes/{telegram_id}_entry.png"

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute(f"SELECT Students.telegramID FROM Students WHERE telegramID = {telegram_id}")
    db_id = cursor.fetchone()

    if db_id:
        cursor.execute("SELECT Students.qrcode_in FROM Students WHERE telegramID = ?", (telegram_id,))
        old_qrcode = cursor.fetchone()
        if old_qrcode and old_qrcode[0]:
            img_data = base64.b64decode(old_qrcode[0])
            img = Image.open(BytesIO(img_data))
            img.save(qr_code_path)
        else:
            # Формируем данные для QR-кода
            qr_data = f"{telegram_id}_{entry_time}"
            # Создаем QR-код
            os.makedirs("qrcodes", exist_ok=True)
            qr = qrcode.QRCode(version=1)
            qr.add_data(qr_data)
            qr.make(fit=True)

            img = qr.make_image(fill_color = "black", back_color = "white")
            img.save(qr_code_path)

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            cursor.execute("UPDATE Students SET qrcode_in = ? WHERE telegramID = ?", (img_base64, telegram_id,))
            conn.commit()

    # Отправляем QR-код пользователю
    await bot.send_photo(message.chat.id, photo=open(qr_code_path, "rb"), caption="Ваш QR-код для входа в университет.")
    conn.close()

# Сканирование QR-кода
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def scan_qr(message: types.Message):
    photo = message.photo[-1]
    photo_path = f"photos/{message.from_user.id}.jpg"
    os.makedirs("photos", exist_ok=True)

    await photo.download(photo_path)

    try:
        img = Image.open(photo_path)
        decoded_data = decode(img)

        if decoded_data:
            data = decoded_data[0].data.decode("utf-8")
            telegram_id, entry_time = data.split("_")

            # Проверка, если QR-код уже был использован или expired
            current_time = int(time.time())
            duration = current_time - int(entry_time)

            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Student WHERE telegramID = ?", (telegram_id,))
            user = cursor.fetchone()

            if user:
                if duration < 300:  # Если прошло меньше 5 минут (например, время действия QR-кода 5 минут)
                    # Студент вошел в университет
                    cursor.execute("UPDATE Student SET in_university = 1, entry_time = ? WHERE telegramID = ?",
                                   (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), telegram_id))
                    conn.commit()
                    await message.reply(f"Добро пожаловать! Вы вошли в университет.")
                else:
                    await message.reply("QR-код просрочен или неверен.")
            else:
                await message.reply("Пользователь не найден.")
            conn.close()
        else:
            await message.reply("Не удалось распознать QR-код.")
    except Exception as e:
        await message.reply(f"Ошибка при обработке изображения: {e}")

# Обработка выхода (когда студент сканирует QR-код для выхода)
@dp.message_handler(lambda message: message.text == "Exit University")
async def exit_university(message: types.Message):
    telegram_id = message.from_user.id

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Student WHERE telegramID = ?", (telegram_id,))
    user = cursor.fetchone()

    if user and user[4]:  # Проверяем, если студент уже в университете
        entry_time = datetime.strptime(user[5], '%Y-%m-%d %H:%M:%S')
        duration = datetime.now() - entry_time

        cursor.execute("UPDATE Student SET in_university = 0 WHERE telegramID = ?", (telegram_id,))
        conn.commit()

        await message.reply(f"Вы провели в университете {duration.total_seconds() // 3600} часов.")
    else:
        await message.reply("Вы не в университете или не зарегистрированы.")

    conn.close()

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)