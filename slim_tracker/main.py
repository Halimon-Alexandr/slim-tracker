from pydub import AudioSegment
import speech_recognition as sr
import pytz
import os
import pickle
import telebot
from telebot import types
from decouple import config
from datetime import datetime, timedelta
from statistics import mean
from decimal import Decimal
kiev_timezone = pytz.timezone("Europe/Kiev")


ADMIN_IDS = config('TG_CHAT_ADMIN').split(',')
API_TOKEN = config('TG_BOT_TOKEN')

bot = telebot.TeleBot(API_TOKEN)

user_data = {}

class UserInfo:
    def __init__(self, gender=None, first_name=None, age=None, height=None, weight=None):
        self.gender = gender
        self.first_name = first_name
        self.age = age
        self.height = height
        self.weight = weight
        self.measurements = []

    def add_measurement(self, age, height, weight):
        today = datetime.now(kiev_timezone).date()
        for measurement in self.measurements:
            if measurement['date'] == today:
                measurement['age'] = age
                measurement['height'] = height
                measurement['weight'] = weight
                break
        else:
            self.measurements.append({
                'date': today,
                'age': age,
                'height': height,
                'weight': weight,
            })

    def calculate_bmi(self):
        return self.weight / ((self.height / 100) ** 2)

    def get_optimal_weight(self):
        min_bmi, max_bmi = 18.5, 24.9
        if self.age < 18:
            if self.gender == '👨':
                if self.age < 6:
                    min_bmi, max_bmi = 14.0, 19.0
                elif self.age < 12:
                    min_bmi, max_bmi = 16.0, 22.0
                else:
                    min_bmi, max_bmi = 17.0, 23.0
            else:
                if self.age < 6:
                    min_bmi, max_bmi = 13.5, 18.5
                elif self.age < 12:
                    min_bmi, max_bmi = 15.5, 21.5
                else:
                    min_bmi, max_bmi = 16.5, 22.5
        else:
            min_weight = min_bmi * (self.height / 100) ** 2
            max_weight = max_bmi * (self.height / 100) ** 2
            return round(min_weight, 1), round(max_weight, 1)

    def get_health_status(self):
        bmi = self.calculate_bmi()
        optimal_weight_range = self.get_optimal_weight()
        status = []
        
        if self.age < 18:
            status.append("Оцінка BMI для дітей та підлітків може бути специфічною.")
        else:
            if bmi < 18.5:
                status.append("Недостатня вага")
            elif 18.5 <= bmi < 24.9:
                status.append("Нормальна вага")
            elif 25.0 <= bmi < 29.9:
                status.append("Надмірна вага")
            elif 30.0 <= bmi < 34.9:
                status.append("Ожиріння 1 ступеня (легке)")
            elif 35.0 <= bmi < 39.9:
                status.append("Ожиріння 2 ступеня (помірне)")
            else:  # bmi >= 40.0
                status.append("Ожиріння 3 ступеня (важке)")
        
        status.append(f"Оптимально для вас: {optimal_weight_range[0]} - {optimal_weight_range[1]} кг")
        return ", ".join(status)

    def get_last_measurements(self):
        today = datetime.now(kiev_timezone).date()
        yesterday = today - timedelta(days=1)
        measurements_today = [m for m in self.measurements if m['date'] == today]
        measurements_yesterday = [m for m in self.measurements if m['date'] == yesterday]
        result = ""
        if measurements_today:
            result += f"Сьогодні: Вага {measurements_today[-1]['weight']} кг\n"
        else:
            result += "Сьогодні: Немає даних\n"
        if measurements_yesterday:
            result += f"Вчора: Вага {measurements_yesterday[-1]['weight']} кг\n"
        else:
            result += "Вчора: Немає даних\n"
        if not measurements_today and not measurements_yesterday:
            last_measurement = sorted(self.measurements, key=lambda m: m['date'], reverse=True)
            if last_measurement:
                last_measurement_date = last_measurement[0]['date']
                result += f"Останній замір: {last_measurement_date.day}.{last_measurement_date.month}\n"
        return result

    def get_weight_difference(self):
        if len(self.measurements) < 2:
            return "Немає достатньо даних для обчислення різниці."
        
        # Сортуємо вимірювання за датою у зворотному порядку
        sorted_measurements = sorted(self.measurements, key=lambda m: m['date'], reverse=True)
        
        # Отримуємо останнє та попереднє вимірювання
        last_measurement = sorted_measurements[0]
        previous_measurement = sorted_measurements[1]
        
        # Використовуємо Decimal для точних обчислень
        last_weight = Decimal(str(last_measurement['weight']))
        previous_weight = Decimal(str(previous_measurement['weight']))
        
        # Обчислюємо різницю
        difference = last_weight - previous_weight
        
        return f"{difference:.2f} кг"

    def get_average_weight_change(self, days):
        today = datetime.now(kiev_timezone).date()
        past_date = today - timedelta(days=days)
        relevant_measurements = [m for m in self.measurements if m['date'] >= past_date]
        if len(relevant_measurements) < 2:
            return f"Немає достатньо даних за останні {days} днів."
        weights = [m['weight'] for m in relevant_measurements]
        total_change = sum(weights[i] - weights[i + 1] for i in range(len(weights) - 1))
        average_change = total_change / (len(weights) - 1)
        if average_change > 0:
            return f"Середній приріст ваги за останні {days} днів: {average_change:.2f} кг"
        elif average_change < 0:
            return f"Середнє зниження ваги за останні {days} днів: {abs(average_change):.2f} кг"
        else:
            return f"Вага залишилась незмінною за останні {days} днів."

    def get_weekly_weight_difference(self):
        today = datetime.now(kiev_timezone).date()
        week_ago = today - timedelta(days=7)
        weights = [Decimal(str(m['weight'])) for m in self.measurements if m['date'] >= week_ago]
        
        if len(weights) < 2:
            return "Немає достатньо даних за останні 7 днів."
        
        initial_weight = weights[0]
        final_weight = weights[-1]
        difference = final_weight - initial_weight
        
        return f"{difference:.2f} кг"

    def get_monthly_weight_difference(self):
        today = datetime.now(kiev_timezone).date()
        month_ago = today - timedelta(days=30)
        weights = [Decimal(str(m['weight'])) for m in self.measurements if m['date'] >= month_ago]
        
        if len(weights) < 2:
            return "Немає достатньо даних за останні 30 днів."
        
        initial_weight = weights[0]
        final_weight = weights[-1]
        difference = final_weight - initial_weight
        
        return f"{difference:.2f} кг"

# Функція для конвертації голосового повідомлення в текст
def recognize_speech(file_path):
    # Шляхи до тимчасових файлів
    ogg_path = file_path
    wav_path = "temp.wav"
    
    # Конвертація OGG в WAV
    audio = AudioSegment.from_ogg(ogg_path)
    audio.export(wav_path, format="wav")
    
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="uk-UA")  # Можна змінити мову за потреби
        return text
    except (sr.UnknownValueError, sr.RequestError):
        return False
    finally:
        # Видалення тимчасових файлів
        if os.path.exists(wav_path):
            os.remove(wav_path)


# Збереження даних у файл
def save_data():
    with open(DATA_FILE, 'wb') as file:
        pickle.dump(user_data, file)

# Відновлення даних з файлу
def load_data():
    global user_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'rb') as file:
            user_data = pickle.load(file)

# Функція для перевірки, чи є користувач адміністратором
def is_admin(user_id):
    return str(user_id) in ADMIN_IDS


def calculate_top_users():
    week_ago = datetime.now(kiev_timezone).date() - timedelta(days=7)
    top_users = []

    for user_id, user_info in user_data.items():
        recent_measurements = [m for m in user_info.measurements if m['date'] >= week_ago]
        if len(recent_measurements) < 2:
            continue

        weights = [Decimal(str(m['weight'])) for m in recent_measurements]
        initial_weight = weights[0]
        final_weight = weights[-1]

        try:
            if initial_weight == Decimal('0'):
                percentage_change = Decimal('inf')  # Avoid division by zero
            else:
                percentage_change = ((final_weight - initial_weight) / initial_weight) * Decimal('100')
        except InvalidOperation:
            percentage_change = Decimal('inf')

        if percentage_change < 0:
            status = "зменшення ваги на"
        elif percentage_change > 0:
            status = "збільшення ваги на"
        else:
            status = "без змін"
        
        top_users.append((user_info.first_name, percentage_change, status))

    top_users.sort(key=lambda x: x[1])
    
    return top_users


@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = message.from_user.id
    if user_id in user_data:
        bot.send_message(message.chat.id, "Ти вже зареєстрований!")
        show_main_menu(message)
    else:
        bot.send_message(message.chat.id, "Привіт, наш улюблений ласун! 🍩😋\nЯкщо ти готовий до змін і хочеш разом з нами досягти нових висот, я тут, щоб підтримати тебе на кожному кроці. 💪🚀\nРазом ми подолаємо зайві кілограми і зробимо цей шлях цікавим і результативним! 🌟🎉")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add('👨', '👩')
        bot.send_message(message.chat.id, "Щоб ми могли правильно розрахувати твій ІМТ (індекс маси тіла), будь ласка, вибери свою стать, натиснувши на відповідну кнопку нижче. 👇😊", reply_markup=markup)
        bot.register_next_step_handler(message, process_gender)

def process_gender(message):
    gender = message.text.lower()
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    user_data[user_id] = UserInfo(gender=gender, first_name=first_name)

    bot.send_message(message.chat.id, "Введи будь ласка свій вік ✏️.\nОбіцяємо, це залишиться між нами! 😉")
    bot.register_next_step_handler(message, process_age)

def process_age(message):
    user_id = message.from_user.id
    try:
        age = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Будь ласка, введи вік в числовому форматі!")
        bot.register_next_step_handler(message, process_age)
        return

    user_data[user_id].age = age

    bot.send_message(message.chat.id, "Тепер введи свій зріст в сантиметрах ✏️.")
    bot.register_next_step_handler(message, process_height)

def process_height(message):
    user_id = message.from_user.id
    try:
        height = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Будь ласка, введи зріст в числовому форматі!")
        bot.register_next_step_handler(message, process_height)
        return

    user_data[user_id].height = height

    bot.send_message(message.chat.id, "А тепер, наостанок, введи свою вагу в кілограмах ✏️.")
    bot.register_next_step_handler(message, process_weight)

def process_weight(message):
    user_id = message.from_user.id
    try:
        weight = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Будь ласка, введи вагу в числовому форматі!")
        bot.register_next_step_handler(message, process_weight)
        return

    user_info = user_data[user_id]
    user_info.weight = weight
    
    # Додати нові виміри до списку
    user_info.add_measurement(age=user_info.age, height=user_info.height, weight=weight)
    
    bot.send_message(message.chat.id, "Вітаю на борту! 🚀\nТепер ти офіційно в нашій команді супергероїв зі схуднення!\nГотовий до нових звершень? 😎")
    save_data()
    show_main_menu(message)


def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add('Мій профіль 👤', 'Внести заміри 📏', 'Найкращі результати 🏆')
    bot.send_message(message.chat.id, "Головне меню:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Мій профіль 👤")
def show_user_info(message):
    user_id = message.from_user.id
    if user_id in user_data:
        user_info = user_data[user_id]

        last_measurements = user_info.get_last_measurements()
        weight_difference = user_info.get_weight_difference()
        weekly_weight_difference = user_info.get_weekly_weight_difference()
        monthly_weight_difference = user_info.get_monthly_weight_difference()
        health_status = user_info.get_health_status()

        response = (f"Ім'я: {user_info.first_name}\n"
                    f"Стать: {user_info.gender.capitalize()}\n"
                    f"Вік: {user_info.age}\n"
                    f"Зріст: {user_info.height} см\n"
                    f"Вага: {user_info.weight} кг\n"
                    f"{health_status}\n\n"
                    f"Останні заміри:\n{last_measurements}\n"
                    f"Різниця ваги між останнім і передостаннім заміром: {weight_difference}\n\n"
                    f"Різниця ваги за останні 7 днів: {weekly_weight_difference}\n"
                    f"Різниця ваги за останні 30 днів: {monthly_weight_difference}")

        bot.send_message(message.chat.id, response)
    else:
        bot.send_message(message.chat.id, "Ти ще не зареєстрований. Будь ласка, почни з реєстрації.")


@bot.message_handler(func=lambda message: message.text == "Внести заміри 📏")
def input_measurements(message):
    user_id = message.from_user.id
    if user_id in user_data:
        user_info = user_data[user_id]

        bot.send_message(message.chat.id, f"Ваш поточний вік: {user_info.age}. Якщо він не змінився, натисніть кнопку 'Далі', або введіть нове значення.")
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('Далі')
        bot.register_next_step_handler(message, process_measurement_age)
        bot.send_message(message.chat.id, "Вік:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Ти ще не зареєстрований. Будь ласка, почни з реєстрації.")

def process_measurement_age(message):
    user_id = message.from_user.id
    if message.text == 'Далі':
        age = user_data[user_id].age
    else:
        try:
            age = int(message.text)
        except ValueError:
            bot.send_message(message.chat.id, "Будь ласка, введи вік в числовому форматі!")
            bot.register_next_step_handler(message, process_measurement_age)
            return

    user_data[user_id].age = age
    bot.send_message(message.chat.id, f"Ваш поточний зріст: {user_data[user_id].height} см. Якщо він не змінився, натисніть кнопку 'Далі', або введіть нове значення.")
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add('Далі')
    bot.register_next_step_handler(message, process_measurement_height)
    bot.send_message(message.chat.id, "Зріст:", reply_markup=markup)

def process_measurement_height(message):
    user_id = message.from_user.id
    if message.text == 'Далі':
        height = user_data[user_id].height
    else:
        try:
            height = float(message.text)
        except ValueError:
            bot.send_message(message.chat.id, "Будь ласка, введи зріст в числовому форматі!")
            bot.register_next_step_handler(message, process_measurement_height)
            return

    user_data[user_id].height = height

    bot.send_message(message.chat.id, f"Ваша поточна вага: {user_data[user_id].weight} кг. Якщо вона не змінилась, натисніть кнопку 'Далі', або введіть нове значення.")
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    markup.add('Далі')
    bot.register_next_step_handler(message, process_measurement_weight)
    bot.send_message(message.chat.id, "Вага:", reply_markup=markup)

def process_measurement_weight(message):
    user_id = message.from_user.id
    if message.text == 'Далі':
        weight = user_data[user_id].weight
    else:
        try:
            weight = float(message.text)
        except ValueError:
            bot.send_message(message.chat.id, "Будь ласка, введи вагу в числовому форматі!")
            bot.register_next_step_handler(message, process_measurement_weight)
            return

    user_data[user_id].weight = weight
    user_data[user_id].add_measurement(user_data[user_id].age, user_data[user_id].height, user_data[user_id].weight)
    save_data()

    bot.send_message(message.chat.id, "Дані збережені!")
    show_main_menu(message)

@bot.message_handler(func=lambda message: message.text == "Найкращі результати 🏆")
def show_top_users(message):
    top_users = calculate_top_users()
    if not top_users:
        bot.send_message(message.chat.id, "Немає достатньо даних для відображення найкращих результатів.")
        return
    
    response = "Найкращі результати за останній тиждень:\n\n"
    for i, (name, weight_change, status) in enumerate(top_users, start=1):
        response += f"{i}. {name} - {status} {abs(weight_change):.2f} % \n"

    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['ім\'я'])
def handle_name_change(message):
    user_id = message.from_user.id
    if user_id in user_data:
        text = message.text.strip().split()
        if len(text) > 1:  # Перевіряємо, чи введено нове ім'я
            new_first_name = ' '.join(text[1:])  # Збираємо нове ім'я з решти слів
            user_data[user_id].first_name = new_first_name
            bot.send_message(message.chat.id, f"Ваше ім'я було змінено на {new_first_name}.")
            save_data()
        else:
            bot.send_message(message.chat.id, "Неправильний формат команди. Використовуйте команду у форматі: /ім'я Ваше нове ім'я.")
    else:
        bot.send_message(message.chat.id, "Ви ще не зареєстровані. Будь ласка, спочатку зареєструйтесь.")


# Обробник для всіх повідомлень, що не були перехоплені іншими обробниками
@bot.message_handler(func=lambda message: True)
def handle_unhandled_messages(message):
    user_id = message.from_user.id
    
    # Перевірка, чи користувач адміністратор
    if is_admin(user_id):
        # Пересилання повідомлення всім адміністраторам, крім самого себе
        for admin_id in ADMIN_IDS:
            if int(admin_id) != user_id:
                if message.voice:
                    bot.send_voice(admin_id, message.voice.file_id, caption=f"{message.text}")
                else:
                    # Якщо голосового повідомлення немає, просто надсилаємо текст
                    bot.send_message(admin_id, message.text)
    else:
        show_main_menu(message)

@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    # Отримання інформації про файл
    file_info = bot.get_file(message.voice.file_id)
    file_path = bot.download_file(file_info.file_path)
    temp_file = "voice_message.ogg"  # Тимчасовий файл для збереження голосового повідомлення
    
    # Збереження голосового повідомлення
    with open(temp_file, 'wb') as file:
        file.write(file_path)
    
    # Конвертація голосового повідомлення у текст
    text = recognize_speech(temp_file)
    
    if text is False:
        text = "Не вдалось розпізнати повідомлення."
    # Видалення тимчасового файлу після конвертації
    os.remove(temp_file)
    
    # Далі обробляємо текст так само, як і текстові повідомлення
    message.text = text
    handle_unhandled_messages(message)


if __name__ == "__main__":
    DATA_FILE = "user_data.pickle"
    load_data()
    bot.polling(none_stop=True)
