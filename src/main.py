# -*- coding: utf-8 -*-
import flet as ft
import json
import os
import pyautogui
from datetime import datetime
import threading
import telebot
import base64
from google import genai
from google.genai import types
import re
from io import BytesIO

# Файлы для сохранения данных
INSTRUCTION_FILE = "instruction.json"
TELEGRAM_TOKEN_FILE = "telegram_token.json"
GEMINI_TOKEN_FILE = "gemini_token.json"

# Глобальные переменные
saved_instruction = ""
telegram_token = ""
gemini_token = ""
bot = None
is_bot_running = False
bot_thread = None

def load_instruction():
    """Загружает инструкцию из файла"""
    global saved_instruction
    try:
        if os.path.exists(INSTRUCTION_FILE):
            with open(INSTRUCTION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                saved_instruction = data.get('instruction', '')
                return saved_instruction
    except Exception as e:
        print(f"Ошибка загрузки инструкции: {e}")
    return ""

def save_instruction_to_file(instruction):
    """Сохраняет инструкцию в файл"""
    try:
        with open(INSTRUCTION_FILE, 'w', encoding='utf-8') as f:
            json.dump({'instruction': instruction}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения инструкции: {e}")
        return False

def load_telegram_token():
    """Загружает токен Telegram из файла"""
    global telegram_token
    try:
        if os.path.exists(TELEGRAM_TOKEN_FILE):
            with open(TELEGRAM_TOKEN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                telegram_token = data.get('token', '')
                return telegram_token
    except Exception as e:
        print(f"Ошибка загрузки токена Telegram: {e}")
    return ""

def save_telegram_token(token):
    """Сохраняет токен Telegram в файл"""
    try:
        with open(TELEGRAM_TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump({'token': token}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения токена Telegram: {e}")
        return False

def load_gemini_token():
    """Загружает токен Gemini из файла"""
    global gemini_token
    try:
        if os.path.exists(GEMINI_TOKEN_FILE):
            with open(GEMINI_TOKEN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                gemini_token = data.get('token', '')
                return gemini_token
    except Exception as e:
        print(f"Ошибка загрузки токена Gemini: {e}")
    return ""

def save_gemini_token(token):
    """Сохраняет токен Gemini в файл"""
    try:
        with open(GEMINI_TOKEN_FILE, 'w', encoding='utf-8') as f:
            json.dump({'token': token}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения токена Gemini: {e}")
        return False

def take_screenshot_as_bytes():
    """Делает скриншот и возвращает его байты"""
    try:
        screenshot = pyautogui.screenshot()
        # Сохраняем скриншот в буфер в памяти
        buffer = BytesIO()
        screenshot.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        print(f"Ошибка создания скриншота: {e}")
        return None

def generate_report_with_gemini(image_bytes, instruction):
    """Генерирует отчёт с помощью Gemini API"""
    global gemini_token
    if not gemini_token:
        return "❌ Ошибка: Gemini API токен не сохранён."

    try:
        client = genai.Client(api_key=gemini_token)
        model = "gemini-2.0-flash"
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=instruction),
                    types.Part.from_bytes(
                        mime_type="image/png",
                        data=image_bytes,
                    ),
                ],
            ),
        ]
        
        full_report = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents
        ):
            full_report += chunk.text
        
        return full_report
        
    except Exception as e:
        print(f"❌ Ошибка при обращении к Gemini API: {e}")
        return f"❌ Ошибка при обращении к Gemini API: {e}"

def escape_markdown(text):
    """Экранирует специальные символы в тексте для MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(r'([%s])' % re.escape(escape_chars), r'\\\1', text)

# --- Обработчики Telegram с использованием telebot ---
def telegram_bot_worker():
    global bot, is_bot_running

    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton('Сформировать отчёт'))

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.send_message(
            message.chat.id,
            "Привет! Я готов к работе. Нажми на кнопку, чтобы сформировать отчёт.",
            reply_markup=keyboard
        )
    
    @bot.message_handler(func=lambda message: message.text == 'Сформировать отчёт')
    def handle_report_button(message):
        global saved_instruction, gemini_token
        
        if not gemini_token:
            bot.send_message(
                message.chat.id, 
                "❌ Gemini API токен не сохранен. Используй GUI-приложение для сохранения."
            )
            return

        if not saved_instruction:
            bot.send_message(
                message.chat.id, 
                "❌ Инструкция для отчёта не сохранена. Используй GUI-приложение для сохранения."
            )
            return

        bot.send_message(message.chat.id, "🤖 Делаю скриншот и отправляю в Gemini...")
        
        screenshot_bytes = take_screenshot_as_bytes()
        if not screenshot_bytes:
            bot.send_message(message.chat.id, "❌ Ошибка: не удалось сделать скриншот.")
            return

        try:
            report_text = generate_report_with_gemini(screenshot_bytes, saved_instruction)
            
            # Удаляем символы ``` из текста отчёта
            cleaned_report_text = report_text.replace("```", "")
            
            # Экранируем оставшиеся специальные символы для Markdown
            escaped_report_text = escape_markdown(cleaned_report_text)
            
            # Отправка скриншота с отчётом в подписи
            bot.send_photo(
                message.chat.id,
                photo=screenshot_bytes,
                caption=f"{escaped_report_text}",
                parse_mode='MarkdownV2'
            )
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка отправки отчёта: {e}")
    
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"❌ Ошибка в потоке бота: {e}")
    finally:
        is_bot_running = False

def main(page: ft.Page):
    page.title = "Настройка инструкции и Telegram/Gemini ботов"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    
    global saved_instruction, telegram_token, gemini_token, bot, is_bot_running, bot_thread
    
    saved_instruction = load_instruction()
    telegram_token = load_telegram_token()
    gemini_token = load_gemini_token()
    
    status_indicator = ft.Text(size=14, weight=ft.FontWeight.BOLD)
    bot_control_button = ft.ElevatedButton()

    def update_bot_status_ui():
        if is_bot_running:
            status_indicator.value = "Бот: Запущен ✅"
            status_indicator.color = "green"
            bot_control_button.text = "Остановить"
            bot_control_button.bgcolor = "red"
        else:
            status_indicator.value = "Бот: Остановлен ❌"
            status_indicator.color = "red"
            bot_control_button.text = "Запустить"
            bot_control_button.bgcolor = "green"
        page.update()

    def start_bot():
        global bot, is_bot_running, telegram_token, bot_thread
        if not telegram_token:
            status_text.value = "❌ Не могу запустить. Сначала сохраните токен Telegram."
            status_text.color = "red"
            page.update()
            return
        
        try:
            bot = telebot.TeleBot(telegram_token)
            bot_thread = threading.Thread(target=telegram_bot_worker, daemon=True)
            bot_thread.start()
            is_bot_running = True
            update_bot_status_ui()
            print("✅ Telegram-бот запущен.")
        except Exception as e:
            status_text.value = f"❌ Ошибка запуска бота: {e}"
            status_text.color = "red"
            is_bot_running = False
            update_bot_status_ui()
            print(f"❌ Ошибка запуска бота: {e}")

    def stop_bot():
        global bot, is_bot_running, bot_thread
        if bot:
            bot.stop_polling()
            if bot_thread and bot_thread.is_alive():
                bot_thread.join(timeout=5)
            is_bot_running = False
            update_bot_status_ui()
            print("❌ Бот остановлен.")
        
    def toggle_bot_status(e):
        if is_bot_running:
            stop_bot()
        else:
            start_bot()

    # Поле ввода токена Telegram
    telegram_token_field = ft.TextField(
        label="Токен Telegram бота",
        hint_text="Введите токен вашего Telegram бота...",
        password=True,
        expand=True,
        value=telegram_token,
    )

    # Поле ввода токена Gemini
    gemini_token_field = ft.TextField(
        label="Токен Gemini API",
        hint_text="Введите токен Gemini API...",
        password=True,
        expand=True,
        value=gemini_token,
    )
    
    # Поле ввода инструкции
    instruction_field = ft.TextField(
        label="Инструкция для Gemini",
        hint_text="Введите промпт для нейросети (например: 'Сделай подробный отчет по скриншоту')...",
        multiline=True,
        min_lines=3,
        max_lines=10, 
        expand=True,
        value=saved_instruction,
    )
    
    status_text = ft.Text("", size=14)
    saved_instruction_text = ft.Text(
        f"Сохраненная инструкция: {saved_instruction[:50]}..." if saved_instruction else "",
        size=12, 
        color="blue"
    )

    def save_instruction(e):
        global saved_instruction
        if not instruction_field.value:
            status_text.value = "❌ Пожалуйста, введите инструкцию!"
            status_text.color = "red"
        else:
            saved_instruction = instruction_field.value
            if save_instruction_to_file(saved_instruction):
                status_text.value = "✅ Инструкция сохранена!"
                status_text.color = "green"
                saved_instruction_text.value = (
                    f"Сохраненная инструкция: {saved_instruction[:50]}..."
                )
            else:
                status_text.value = "❌ Ошибка сохранения в файл!"
                status_text.color = "red"
        
        page.update()
    
    def save_telegram_token_handler(e):
        global telegram_token
        if not telegram_token_field.value:
            status_text.value = "❌ Пожалуйста, введите токен Telegram!"
            status_text.color = "red"
        else:
            telegram_token = telegram_token_field.value
            if save_telegram_token(telegram_token):
                status_text.value = "✅ Токен Telegram сохранен!"
                status_text.color = "green"
                if is_bot_running:
                    stop_bot()
                    start_bot()
            else:
                status_text.value = "❌ Ошибка сохранения токена Telegram!"
                status_text.color = "red"
        page.update()
    
    def save_gemini_token_handler(e):
        global gemini_token
        if not gemini_token_field.value:
            status_text.value = "❌ Пожалуйста, введите токен Gemini!"
            status_text.color = "red"
        else:
            gemini_token = gemini_token_field.value
            if save_gemini_token(gemini_token):
                status_text.value = "✅ Токен Gemini сохранен!"
                status_text.color = "green"
            else:
                status_text.value = "❌ Ошибка сохранения токена Gemini!"
                status_text.color = "red"
        page.update()
    
    def clear_instruction(_):
        global saved_instruction
        saved_instruction = ""
        instruction_field.value = ""
        status_text.value = "🗑️ Инструкция очищена!"
        status_text.color = "orange"
        saved_instruction_text.value = ""
        
        try:
            if os.path.exists(INSTRUCTION_FILE):
                os.remove(INSTRUCTION_FILE)
        except Exception as e:
            print(f"Ошибка удаления файла: {e}")
        
        page.update()
    
    save_instruction_button = ft.ElevatedButton(
        text="Сохранить",
        icon="SAVE",
        on_click=save_instruction,
        expand=True
    )
    
    clear_instruction_button = ft.ElevatedButton(
        text="Очистить",
        icon="DELETE",
        on_click=clear_instruction,
        expand=True
    )
    
    save_telegram_token_button = ft.ElevatedButton(
        text="Сохранить токен",
        icon="SAVE",
        on_click=save_telegram_token_handler
    )

    save_gemini_token_button = ft.ElevatedButton(
        text="Сохранить токен",
        icon="SAVE",
        on_click=save_gemini_token_handler
    )

    bot_control_button.on_click = toggle_bot_status
    update_bot_status_ui()
    
    if telegram_token:
        start_bot()

    page.add(
        ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "🤖 Настройка Telegram и Gemini ботов",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=10),
                    ft.Row(
                        controls=[
                            telegram_token_field,
                            save_telegram_token_button,
                            bot_control_button
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=10
                    ),
                    ft.Container(height=10),
                    ft.Row(
                        controls=[
                            gemini_token_field,
                            save_gemini_token_button
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=10
                    ),
                    ft.Container(height=20),
                    ft.Divider(height=20),
                    ft.Row(
                        controls=[
                            status_indicator,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    ft.Divider(height=20),
                    ft.Text(
                        "Инструкция для отчётов Gemini",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=10),
                    instruction_field,
                    ft.Container(height=20),
                    ft.Row(
                        controls=[
                            save_instruction_button, 
                            clear_instruction_button
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=20
                    ),
                    ft.Container(height=20),
                    status_text,
                    ft.Container(height=10),
                    saved_instruction_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            alignment=ft.alignment.center,
        )
    )

ft.app(target=main)