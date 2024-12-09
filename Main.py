import time
import sqlite3
import base64
import qrcode
import os
from io import BytesIO
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from PIL import Image
from pyzbar.pyzbar import decode
from datetime import datetime

# Установка токена
API_TOKEN = "8127623558:AAEfPnFvcOrTkGqdvLheCdtMEB5Us5RFQb8"

# Создаем бота и диспетчер
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Кнопки
kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Get ID"), KeyboardButton(text="Generate QR Code")],
        [KeyboardButton(text="Exit University")]
    ],
    resize_keyboard=True
)

# Подключение к базе данных
db_file = "university.db"

# Команда /start
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=kb)

# Обработка команды Get ID
@dp.message(F.text == "Get ID")
async def get_id(message: types.Message):
    telegram_id = message.from_user.id
    await message.answer(f"Ваш Telegram ID: {telegram_id}")

# Генерация QR-кода с меткой времени
@dp.message(lambda message: message.text == "Generate QR Code")
async def generate_qr_code(message: types.Message):
    telegram_id = message.from_user.id
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

            img = qr.make_image(fill_color="black", back_color="white")
            img.save(qr_code_path)

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            cursor.execute("UPDATE Students SET qrcode_in = ? WHERE telegramID = ?", (img_base64, telegram_id,))
            conn.commit()

    # Отправляем QR-код пользователю
    await bot.send_photo(message.chat.id, photo=FSInputFile(qr_code_path), caption="Ваш QR-код для входа в университет.")
    conn.close()


# Сканирование QR-кода
@dp.message(F.content_type == types.ContentType.PHOTO)
async def scan_qr(message: types.Message):
    photo = message.photo[-1]
    photo_path = f"photos/{message.from_user.id}.jpg"
    os.makedirs("photos", exist_ok=True)

    await photo.download(destination_file=photo_path)

    try:
        img = Image.open(photo_path)
        decoded_data = decode(img)

        if decoded_data:
            # Попытка распознать данные QR-кода
            data = decoded_data[0].data.decode("utf-8")

            try:
                # Разделяем данные на telegram_id и entry_time
                telegram_id, entry_time = data.split("_")
                telegram_id = int(telegram_id)
                entry_time = int(entry_time)
            except ValueError:
                await message.answer("Ошибка в формате данных QR-кода.")
                return

            # Проверяем время действия QR-кода
            current_time = int(time.time())
            duration = current_time - entry_time

            if duration > 300:  # Если прошло больше 5 минут
                await message.answer("QR-код просрочен или неверен.")
                return

            # Работа с базой данных
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Students WHERE telegramID = ?", (telegram_id,))
            user = cursor.fetchone()

            if user:
                # Обновляем статус in_university
                cursor.execute("UPDATE Students SET in_university = 1 WHERE telegramID = ?", (telegram_id,))
                conn.commit()
                await message.answer("Ваш статус обновлен: вы вошли в университет.")
            else:
                await message.answer("Пользователь не найден.")
            conn.close()
        else:
            await message.answer("Не удалось распознать QR-код.")
    except Exception as e:
        await message.answer(f"Ошибка при обработке изображения: {e}")

# Обработка данных QR-кода, отправленных текстом
@dp.message(F.text.regexp(r"^\d+_\d+$"))  # Регулярное выражение для проверки формата
async def process_qr_text(message: types.Message):
    try:
        data = message.text
        telegram_id, entry_time = map(int, data.split("_"))

        # Проверяем время действия QR-кода
        current_time = int(time.time())
        duration = current_time - entry_time

        if duration > 300:  # Если прошло больше 5 минут
            await message.answer("QR-код просрочен или неверен.")
            return

        # Работа с базой данных
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Students WHERE telegramID = ?", (telegram_id,))
        user = cursor.fetchone()

        if user:
            # Обновляем статус in_university
            cursor.execute("UPDATE Students SET in_university = 1 WHERE telegramID = ?", (telegram_id,))
            conn.commit()
            await message.answer("Ваш статус обновлен: вы вошли в университет.")
        else:
            await message.answer("Пользователь не найден.")
        conn.close()
    except Exception as e:
        await message.answer(f"Ошибка при обработке данных: {e}")


from datetime import datetime

# Обработка выхода (Exit University)
@dp.message(F.text == "Exit University")
async def exit_university(message: types.Message):
    telegram_id = message.from_user.id

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Students WHERE telegramID = ?", (telegram_id,))
    user = cursor.fetchone()

    if user and user[4]:  # Проверяем, если студент уже в университете
        # Если entry_time хранится как метка времени (int)
        entry_time = datetime.fromtimestamp(user[5])  # Конвертируем из timestamp
        duration = datetime.now() - entry_time

        # Обновляем статус выхода
        cursor.execute("UPDATE Students SET in_university = 0 WHERE telegramID = ?", (telegram_id,))
        conn.commit()

        await message.answer(f"Вы провели в университете {duration.total_seconds() // 3600:.0f} часов.")
    else:
        await message.answer("Вы не в университете или не зарегистрированы.")

    conn.close()


if __name__ == "__main__":
    # Запускаем бота
    dp.run_polling(bot)
