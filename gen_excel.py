import sqlite3
import pandas as pd
from datetime import datetime
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl import load_workbook
import requests

# Подключение к базе данных SQLite
db_path = 'university.db'
conn = sqlite3.connect(db_path)

# Запрос для объединения таблиц
query = """
SELECT *
FROM Students AS s
INNER JOIN `Group` AS g ON s.groupID = g.groupID
INNER JOIN Schedule AS sch ON g.scheduleID = sch.rowid
"""

# Выполнение запроса и загрузка данных в DataFrame
df_merged = pd.read_sql(query, conn)

# Закрытие соединения с базой данных
conn.close()

# Переименование столбцов
df_cleaned = df_merged.rename(columns={
    'student_name': 'ФИО',
    'group_name': 'Группа',
    'Monday_hours': 'Понеделник_часы',
    'Tuesday_hours': 'Вторник_часы',
    'Wednesday_hours': 'Среда_часы',
    'Thursday_hours': 'Четверг_часы',
    'Friday_hours': 'Пятница_часы',
    'Saturday_hours': 'Суббота_часы'
})

# Удаление ненужных столбцов
columns_to_drop = ['groupID', 'scheduleID', 'telegramID', 'qrcode_in', 'qrcode_out', 'in_university']
df_cleaned = df_cleaned.drop(columns=columns_to_drop)

# Упорядочивание столбцов
column_order = ['ФИО', 'Группа',
                'Понеделник_часы', 'Вторник_часы', 'Среда_часы',
                'Четверг_часы', 'Пятница_часы', 'Суббота_часы']
df_cleaned = df_cleaned[column_order]

# Преобразование столбца 'Группа' в строковый тип для корректной сортировки
df_cleaned['Группа'] = df_cleaned['Группа'].astype(str)

# Сортировка по группе
df_cleaned = df_cleaned.sort_values(by='Группа')

# Генерация имени файла с текущей датой
current_date = datetime.now().strftime('%Y-%m-%d')
output_file = f'отчёт_посещаемости_за_{current_date}.xlsx'

# Сохранение данных в Excel
with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    # Запись DataFrame в Excel
    df_cleaned.to_excel(writer, index=False, sheet_name='Merged Schedule')

    # Получение объекта книги
    workbook = writer.book
    worksheet = workbook['Merged Schedule']

    # Установка ширины столбцов по ширине заголовков и индивидуальные изменения
    for col in worksheet.columns:
        column = col[0].column_letter
        max_length = len(str(col[0].value)) + 2
        worksheet.column_dimensions[column].width = max_length

    column_width = max(df_cleaned['ФИО'].apply(lambda x: len(str(x)))) + 2
    worksheet.column_dimensions['A'].width = column_width

print(f"Объединённые данные успешно сохранены в файл '{output_file}'.")

TOKEN = "8127623558:AAEfPnFvcOrTkGqdvLheCdtMEB5Us5RFQb8"
# ID получателя (Ваш Telegram ID)
CHAT_ID = '6749710621'


# Отправка файла через Telegram Bot API
def send_file_to_telegram(file_path, chat_id, token):
    url = f'https://api.telegram.org/bot{token}/sendDocument'

    with open(file_path, 'rb') as file:
        files = {'document': file}
        data = {'chat_id': chat_id}

        response = requests.post(url, data=data, files=files)

        if response.status_code == 200:
            print(f"Файл '{file_path}' успешно отправлен на Telegram.")
        else:
            print(f"Ошибка при отправке файла: {response.status_code}, {response.text}")


# Отправка файла
send_file_to_telegram(output_file, CHAT_ID, TOKEN)
