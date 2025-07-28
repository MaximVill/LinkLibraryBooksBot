import telebot
from telebot import types
import sqlite3

# Инициализация бота
API_TOKEN = '7570954937:AAEyuXmEkY_GM3rm6gT_luGpXhNe4eEZ2Hg'
bot = telebot.TeleBot(API_TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('library.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы для хранения книг
cursor.execute('''
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    source_link TEXT,
    summary TEXT,
    tags TEXT,
    date_added DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# Глобальные переменные для временного хранения данных
current_user_data = {}
user_states = {}  # Хранение состояния пользователя


# Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("➕ Добавить книгу"))

    btn2 = types.KeyboardButton("📚 Список")
    btn3 = types.KeyboardButton("🔎 Поиск")
    markup.row(btn2, btn3)

    markup.add(types.KeyboardButton("❌ Удалить книгу"))

    bot.send_message(message.chat.id, "Привет! Я бот-библиотека. Добавь свою первую книгу.", reply_markup=markup)


# Команда /help
@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
📚 *Доступные команды и кнопки*:

📌 **Команды:**
- /start — начать работу с ботом
- /cancel — отменить текущее действие (например, добавление или удаление книги)
- /stats — посмотреть статистику прочитанных книг
- /help — открыть это руководство

📌 **Кнопки:**
- "Добавить книгу" — добавить новую книгу в библиотеку
- "Список" — посмотреть список всех добавленных книг (с ID, названием, автором, тегами)
- "Поиск" — найти книгу по названию или тегу
- "Удалить книгу" — удалить книгу по её ID

📝 **Как использовать?**
При добавлении книги указывайте теги через запятую, например:  
`развитие, личностный рост`

🔍 **Поиск**  
Вы можете искать как по части названия, так и по любому из тегов. Поиск не чувствителен к регистру.

🚫 **Важно:**  
Если вы начали добавлять или удалять книгу, то для выполнения другого действия — завершите или отмените текущее.

💡 Совет: используйте /cancel, если хотите прервать ввод данных.
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')


# Команда /cancel - отмена текущего действия
@bot.message_handler(commands=['cancel'])
def cancel_action(message):
    chat_id = message.chat.id
    if user_states.get(chat_id) == "adding_book":
        user_states[chat_id] = None
        bot.send_message(chat_id, "Добавление книги отменено.")
    elif user_states.get(chat_id) == "deleting_book":
        user_states[chat_id] = None
        bot.send_message(chat_id, "Удаление книги отменено.")
    else:
        bot.send_message(chat_id, "Нет активного действия для отмены.")


# Команда /stats - статистика чтения
@bot.message_handler(commands=['stats'])
def show_stats(message):
    cursor.execute("SELECT COUNT(*) FROM books")
    total_books = cursor.fetchone()[0]

    cursor.execute("SELECT tags FROM books")
    tags = cursor.fetchall()
    tag_counts = {}
    for tag_list in tags:
        for tag in tag_list[0].split(','):
            tag = tag.strip()
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

    stats = f"Всего книг: {total_books}\n\nПопулярные теги:\n"
    for tag, count in tag_counts.items():
        stats += f"- {tag}: {count}\n"

    bot.send_message(message.chat.id, stats)


# Обработчик текстовых сообщений для кнопок
@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    chat_id = message.chat.id
    current_state = user_states.get(chat_id)

    # Если пользователь пытается начать новое действие, пока уже выполняет другое
    if current_state == "adding_book":
        if message.text in ["📚 Список", "🔎 Поиск", "❌ Удалить книгу"]:
            bot.send_message(chat_id, """
⚠️ *Обнаружена попытка переключения!*  
Пожалуйста, завершите добавление книги или отмените действие:  
➡️ Введите корректное значение  
➡️ Или воспользуйтесь командой /cancel  
❓ Дополнительная помощь: [/help](/help)
""", parse_mode='Markdown')
            return
        else:
            # Если это не одна из запрещённых кнопок, то продолжаем
            pass
    elif current_state == "deleting_book":
        if message.text in ["➕ Добавить книгу", "📚 Список", "🔎 Поиск"]:
            bot.send_message(chat_id, """
⚠️ *Обнаружена попытка переключения!*  
Вы сейчас в процессе удаления книги.  
Завершите или отмените текущее действие перед выполнением нового.
""")
            return

    # Обработка самих кнопок
    if message.text == "➕ Добавить книгу":
        user_states[chat_id] = "adding_book"
        add_book_start(message)
    elif message.text == "📚 Список":
        list_books(message)
    elif message.text == "🔎 Поиск":
        search_books_start(message)
    elif message.text == "❌ Удалить книгу":
        delete_book_start(message)
    else:
        bot.send_message(message.chat.id, "Неизвестная команда. Пожалуйста, используйте кнопки.")


# Команда /add - добавление книги
@bot.message_handler(commands=['add'])
def add_book_start(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите название книги:")
    bot.register_next_step_handler(message, process_title_step)


def process_title_step(message):
    text = message.text.strip()
    if text in ["➕ Добавить книгу", "📚 Список", "🔎 Поиск", "❌ Удалить книгу"]:
        bot.send_message(message.chat.id, """
⚠️ *Обнаружена попытка переключения!*  
Пожалуйста, завершите добавление книги или отмените действие:  
➡️ Введите корректное значение  
➡️ Или воспользуйтесь командой /cancel  
\n❓ Дополнительная помощь: [/help](/help)
""", parse_mode='Markdown')
        return

    current_user_data['title'] = text
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите автора книги:")
    bot.register_next_step_handler(message, process_author_step)
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass


def process_author_step(message):
    current_user_data['author'] = message.text.strip()
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите ссылку на источник (например, электронную версию):")
    bot.register_next_step_handler(message, process_source_step)
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass


def process_source_step(message):
    current_user_data['source_link'] = message.text.strip()
    bot.send_message(message.chat.id, "Напишите краткий пересказ книги:")
    bot.register_next_step_handler(message, process_summary_step)
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass


def process_summary_step(message):
    current_user_data['summary'] = message.text.strip().lower()
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите теги (через запятую):")
    bot.register_next_step_handler(message, process_tags_step)
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass


def process_tags_step(message):
    # Получаем теги от пользователя
    tags_input = message.text.strip().lower()  # Преобразуем в нижний регистр
    # Разделяем теги по запятым и убираем лишние пробелы
    tags_list = [tag.strip() for tag in tags_input.split(',')]
    # Сохраняем теги в базу данных как строку
    current_user_data['tags'] = ', '.join(tags_list)

    cursor.execute('''
    INSERT INTO books (title, author, source_link, summary, tags)
    VALUES (?, ?, ?, ?, ?)
    ''', (
        current_user_data['title'],
        current_user_data['author'],
        current_user_data['source_link'],
        current_user_data['summary'],
        current_user_data['tags']
    ))
    conn.commit()

    bot.send_message(message.chat.id, "Книга успешно добавлена!")
    user_states[message.chat.id] = None  # Сбрасываем состояние
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass


# Команда /list - список всех книг
@bot.message_handler(commands=['list'])
def list_books(message):
    cursor.execute("SELECT id, title, author, source_link, tags FROM books")
    books = cursor.fetchall()
    if not books:
        bot.send_message(message.chat.id, "Список книг пуст.")
    else:
        response = "*Ваши книги:*\n\n"
        for book in books:
            book_id, title, author, link, tags = book
            tag_list = ", ".join([f"`{tag.strip()}`" for tag in tags.split(',')]) if tags else ""
            response += f"ID: {book_id} | {title} ({author})\nСсылка: _{link}_\nТеги: {tag_list}\n\n"
        bot.send_message(message.chat.id, response, parse_mode="Markdown")


# Удаление книги
def delete_book_start(message):
    chat_id = message.chat.id
    user_states[chat_id] = "deleting_book"
    bot.send_message(chat_id, "Введите ID книги, которую хотите удалить:")
    bot.register_next_step_handler(message, delete_book)


def delete_book(message):
    chat_id = message.chat.id
    try:
        book_id = int(message.text.strip())
        cursor.execute("SELECT id FROM books WHERE id = ?", (book_id,))
        if cursor.fetchone():
            cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
            conn.commit()
            bot.send_message(chat_id, f"Книга с ID {book_id} успешно удалена.")
        else:
            bot.send_message(chat_id, "Книга с таким ID не найдена.")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введите корректный ID (число).")
    finally:
        user_states[chat_id] = None  # Сбрасываем состояние


# Команда /search - поиск книги
@bot.message_handler(commands=['search'])
def search_books_start(message):
    bot.send_message(message.chat.id, "Введите название или тег для поиска:")
    bot.register_next_step_handler(message, search_books)


def search_books(message):
    query = message.text.strip().lower()
    cursor.execute('''
        SELECT id, title, author, source_link, tags FROM books 
        WHERE LOWER(title) LIKE ? OR tags LIKE ?
    ''', (f"%{query}%", f"%{query}%"))
    books = cursor.fetchall()

    if not books:
        bot.send_message(message.chat.id, "Книги не найдены.")
    else:
        response = "*Результаты поиска:*\n\n"
        for book in books:
            book_id, title, author, link, tags = book
            tag_list = ", ".join([f"`{tag.strip()}`" for tag in tags.split(',')]) if tags else ""
            response += f"ID: {book_id} | {title} ({author})\nСсылка: _{link}_\nТеги: {tag_list}\n\n"
        bot.send_message(message.chat.id, response, parse_mode="Markdown")


# Запуск бота
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(non_stop=True)