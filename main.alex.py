import asyncio
import os
from collections import defaultdict
from openai import AsyncOpenAI
from telebot.async_telebot import AsyncTeleBot
from openai import AsyncOpenAI
import logging 
import aiohttp
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=logging.getLevelName(log_level), format='%(asctime)s - %(levelname)s - %(message)s')

from tokens import BOT_TOKEN, OPENAI_API_KEY

bot = AsyncTeleBot(BOT_TOKEN)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

MAX_HISTORY = 5

dialog_history = defaultdict(list)

eco_mode = set()
    
def get_start_kb():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            "Спросить об экологии",
            callback_data="eco_mode"
        )
    )
    return kb

@bot.message_handler(commands=['start'])
async def gpt_answer(message):
    await bot.reply_to(
        message,
        """\
Привет! 
Я экологический бот.
Спроси меня про сортировку мусора, защиту природы или снижение выбросов.
""",
        reply_markup=get_start_kb() 
    )

@bot.callback_query_handler(func=lambda call: call.data == "eco_mode")
async def enable_eco(call):
    eco_mode.add(call.from_user.id)

    await bot.send_message(
        call.message.chat.id,
        "Режим экологии включён!"
    )

    await bot.answer_callback_query(call.id)
    


SYSTEM_PROMPT = """
Ты экологический помощник.

Ты отвечаешь только на темы:
- экология
- сортировка мусора
- переработка
- защита природы
- климат
- уменьшение выбросов CO2
- экономия воды и энергии
- устойчивый образ жизни

Если вопрос не относится к экологии —
вежливо скажи, что ты специализируешься только на экологических темах.

Отвечай простым и понятным языком.
"""




@bot.message_handler(func=lambda message: True)
async def echo_message(message):
    user_id = message.from_user.id
    user_text = message.text
    if user_id not in eco_mode:
        await bot.reply_to(message, "Нажми /start и включи режим")
        return

    logging.info(f"Received message from user {user_id}: {user_text}")


    # Добавляем сообщение пользователя в историю
    dialog_history[user_id].append({
        "role": "user",
        "content": user_text
    })

    # Оставляем только последние 5 сообщений
    dialog_history[user_id] = dialog_history[user_id][-MAX_HISTORY:]

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    messages.extend(dialog_history[user_id])

    async def send_typing(): 
        for i in range(20):
            await bot.send_chat_action(message.chat.id, 'typing', timeout=5)
            logging.debug(f"Sent typing action for user {user_id}, iteration {i}")
            await asyncio.sleep(4) 

    send_typing_task = asyncio.create_task(send_typing())
   
    try:
        check_418(user_text)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
        )

        bot_reply = response.choices[0].message.content

        logging.info(f"Received response from OpenAI for user {user_id}: {bot_reply}")

        # Сохраняем ответ бота
        dialog_history[user_id].append({
            "role": "assistant",
            "content": bot_reply
        })

        # Опять обрезаем историю
        dialog_history[user_id] = dialog_history[user_id][-MAX_HISTORY:]

        send_typing_task.cancel() 

        await bot.reply_to(message, bot_reply)

    except Exception as e:
        logging.error(f"Error while processing message from user {user_id}: {str(e)}")

        send_typing_task.cancel() 

        await bot.reply_to(message, f"Ошибка: {str(e)}")

    finally:
        if not send_typing_task.done():
            send_typing_task.cancel()
    

def check_418(text):
        if "418" in text:
            raise Exception("I am a teapot (418) - The server refuses to brew coffee because it is, permanently, a teapot.")

if __name__ == "__main__":
    asyncio.run(bot.polling())
