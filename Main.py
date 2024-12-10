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
        [KeyboardButton(text="QR Code для входа"), KeyboardButton(text="QR Code для выхода")],
        [KeyboardButton(text="Статистика студента"), KeyboardButton(text="Get ID")]
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


# Генерация QR-кода для входа
@dp.message(F.text == "QR Code для входа")
async def generate_entry_qr_code(message: types.Message):
    telegram_id = message.from_user.id
    entry_time = int(time.time())
    qr_code_path = f"qrcodes/{telegram_id}_entry.png"

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT telegramID FROM Students WHERE telegramID = ?", (telegram_id,))
    db_id = cursor.fetchone()

    if db_id:
        qr_data = f"entry_{telegram_id}_{entry_time}"
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

        await bot.send_photo(message.chat.id, photo=FSInputFile(qr_code_path),
                             caption="Ваш QR-код для входа в университет.")
    else:
        await message.answer("Вы не зарегистрированы в системе.")
    conn.close()


# Генерация QR-кода для выхода
@dp.message(F.text == "QR Code для выхода")
async def generate_exit_qr_code(message: types.Message):
    telegram_id = message.from_user.id
    exit_time = int(time.time())
    qr_code_path = f"qrcodes/{telegram_id}_exit.png"

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT telegramID, in_university FROM Students WHERE telegramID = ?", (telegram_id,))
    db_data = cursor.fetchone()

    if db_data and db_data[1] == 1:  # Проверяем, что студент в университете
        qr_data = f"exit_{telegram_id}_{exit_time}"
        os.makedirs("qrcodes", exist_ok=True)
        qr = qrcode.QRCode(version=1)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_code_path)

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        cursor.execute("UPDATE Students SET qrcode_out = ? WHERE telegramID = ?", (img_base64, telegram_id,))
        conn.commit()

        await bot.send_photo(message.chat.id, photo=FSInputFile(qr_code_path),
                             caption="Ваш QR-код для выхода из университета.")
    else:
        await message.answer("Вы либо не зарегистрированы, либо уже вышли из университета.")
    conn.close()


# Сканирование QR-кода (вход или выход)
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
            data = decoded_data[0].data.decode("utf-8")
            action, telegram_id, timestamp = data.split("_")
            telegram_id = int(telegram_id)
            timestamp = int(timestamp)

            # Проверяем время действия QR-кода (5 минут)
            current_time = int(time.time())
            if current_time - timestamp > 300:
                await message.answer("QR-код просрочен или неверен.")
                return

            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Students WHERE telegramID = ?", (telegram_id,))
            user = cursor.fetchone()

            if user:
                if action == "entry":
                    cursor.execute("UPDATE Students SET in_university = 1 WHERE telegramID = ?", (telegram_id,))
                    await message.answer("Ваш статус обновлен: вы вошли в университет.")
                elif action == "exit" and user[4] == 1:
                    cursor.execute("UPDATE Students SET in_university = 0 WHERE telegramID = ?", (telegram_id,))
                    await message.answer("Ваш статус обновлен: вы вышли из университета.")
                else:
                    await message.answer("Действие некорректно. Возможно, вы не находитесь в университете.")
                conn.commit()
            else:
                await message.answer("Пользователь не найден.")
            conn.close()
        else:
            await message.answer("Не удалось распознать QR-код.")
    except Exception as e:
        await message.answer(f"Ошибка при обработке изображения: {e}")


@dp.message(F.text.regexp(r"^(entry|exit)_\d+_\d+$"))
async def process_qr_text(message: types.Message):
    try:
        data = message.text
        action, telegram_id, timestamp = data.split("_")
        telegram_id = int(telegram_id)
        timestamp = int(timestamp)

        # Проверяем срок действия QR-кода
        current_time = int(time.time())
        if current_time - timestamp > 300:
            await message.answer("QR-код просрочен или неверен.")
            return

        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Students WHERE telegramID = ?", (telegram_id,))
        user = cursor.fetchone()

        if user:
            if action == "entry":
                # Обновляем `time_in` и статус
                cursor.execute("UPDATE Students SET time_in = ?, in_university = 1 WHERE telegramID = ?",
                               (timestamp, telegram_id))
                conn.commit()
                await message.answer("Ваш статус обновлен: вы вошли в университет.")
            elif action == "exit" and user[4] == 1:  # Убедимся, что студент уже в университете
                # Получаем `time_in` для расчета
                cursor.execute("SELECT time_in FROM Students WHERE telegramID = ?", (telegram_id,))
                time_in = cursor.fetchone()[0]
                if time_in:
                    # Рассчитываем посещенные часы
                    attended_hours = (timestamp - time_in) / 3600

                    # Получаем недельную нагрузку из таблицы Schedule
                    cursor.execute(""" 
                        SELECT 
                            COALESCE(Monday_hours, 0) + 
                            COALESCE(Tuesday_hours, 0) + 
                            COALESCE(Wednesday_hours, 0) + 
                            COALESCE(Thursday_hours, 0) + 
                            COALESCE(Friday_hours, 0) + 
                            COALESCE(Saturday_hours, 0) 
                        FROM Schedule
                        LIMIT 1;
                    """)
                    weekly_hours = cursor.fetchone()[0]
                    semester_weeks = 16  # Предположим, что семестр длится 16 недель
                    semester_hours = weekly_hours * semester_weeks

                    # Рассчитываем пропущенные часы
                    skipped_hours = max(0, semester_hours - attended_hours)

                    # Обновляем `time_out` и `skipped_hours`
                    cursor.execute("""
                        UPDATE Students 
                        SET time_out = ?, in_university = 0, skipped_hours = skipped_hours + ? 
                        WHERE telegramID = ?
                    """, (timestamp, skipped_hours, telegram_id))
                    conn.commit()

                    await message.answer(f"Ваш статус обновлен: вы вышли из университета. Пропущенные часы обновлены.")
                else:
                    await message.answer("Ошибка: Время входа не найдено.")
            else:
                await message.answer("Действие некорректно. Возможно, вы не находитесь в университете.")
        else:
            await message.answer("Пользователь не найден.")
        conn.close()
    except Exception as e:
        await message.answer(f"Ошибка при обработке данных: {e}")


@dp.message(F.text == "Статистика студента")
async def student_statistics(message: types.Message):
    telegram_id = message.from_user.id
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Получаем расписание (часы за неделю)
    cursor.execute("""
        SELECT 
            COALESCE(Monday_hours, 0) +
            COALESCE(Tuesday_hours, 0) +
            COALESCE(Wednesday_hours, 0) +
            COALESCE(Thursday_hours, 0) +
            COALESCE(Friday_hours, 0) +
            COALESCE(Saturday_hours, 0) AS weekly_hours
        FROM Schedule
        LIMIT 1
    """)
    weekly_hours = cursor.fetchone()[0]

    if not weekly_hours:
        await message.answer("Ошибка: расписание не задано.")
        return

    semester_weeks = 16  # Допустим, семестр длится 16 недель
    semester_hours = weekly_hours * semester_weeks

    # Получаем данные студента
    cursor.execute("""
        SELECT time_in, time_out, skipped_hours 
        FROM Students 
        WHERE telegramID = ?
    """, (telegram_id,))
    student_data = cursor.fetchone()
    conn.close()

    if not student_data:
        await message.answer("Данные о студенте не найдены.")
        return

    time_in, time_out, skipped_hours = student_data

    # Преобразуем временные метки в читаемый формат
    time_in_readable = datetime.fromtimestamp(time_in).strftime('%Y-%m-%d %H:%M:%S') if time_in else "Не зафиксировано"
    time_out_readable = datetime.fromtimestamp(time_out).strftime(
        '%Y-%m-%d %H:%M:%S') if time_out else "Не зафиксировано"

    # Рассчитаем посещенные часы
    attended_hours = 0
    if time_in and time_out:
        attended_hours = (time_out - time_in) / 3600  # Часы посещения

    # Пропущенные часы
    missed_hours = semester_hours - attended_hours

    # Формируем сообщение со статистикой
    stats_message = (
        f"📊 Статистика студента:\n\n"
        f"🕒 Время входа: {time_in_readable}\n"
        f"🕒 Время выхода: {time_out_readable}\n"
        f"✅ Посещено часов: {attended_hours:.2f}\n"
        f"❌ Пропущено часов: {missed_hours:.2f}\n"
        f"📅 Всего часов в неделю: {weekly_hours:.2f}\n"
        f"📅 Всего часов за семестр: {semester_hours:.2f}\n"
    )

    await message.answer(stats_message)


# Обработка команды /report для генерации отчета
@dp.message(Command("report"))
async def report(message: types.Message):
    # Импортируем генерирование отчета только при вызове команды
    import gen_excel

    # Вызываем функцию для генерации отчета (предположим, что она есть в модуле gen_excel)
    await message.answer("Генерация отчета...")
    gen_excel.generate_report()  # Например, вызов функции из модуля gen_excel
    await message.answer("Отчет сгенерирован.")


if __name__ == "__main__":
    # Запускаем бота
    dp.run_polling(bot)
