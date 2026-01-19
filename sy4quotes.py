"""
    📝 Sy4Quotes - Цитаты из канала "Sy4enish"
    
    Модуль для получения случайной цитаты из Telegram-канала @quotesSy4enish
    и генерации парных цитат с помощью Google Gemini.
    
    Для использования функций генерации цитат через Gemini требуется установить
    библиотеку `google-generativeai` и настроить API ключ.
"""

__version__ = (1, 2, 5)

# meta developer: @Xpansee @Sy4enish
# requires: google-generativeai

from .. import loader, utils
from herokutl.types import Message
import logging
import random
import re

try:
    import google.generativeai as genai
except ImportError:
    genai = None # Библиотека не установлена, функционал будет недоступен

logger = logging.getLogger(__name__)

QUOTES_CHANNEL = "quotesSy4enish" # Юзернейм канала с цитатами
MESSAGE_POOL_LIMIT = 100 # Максимальное количество сообщений для парсинга цитат из канала

@loader.tds
class Sy4enishQuotesMod(loader.Module):
    """Цитаты из @quotesSy4enish и генератор парных цитат"""

    strings = {
        "name": "Sy4enishQuotes",
        "fetching": "⏳ Загружаю цитату...",
        "no_quotes": "🚫 Не удалось найти подходящие цитаты в канале.",
        "error": "❌ Произошла ошибка: {}",
        "channel_not_found": "🚫 Канал '{}' не найден или недоступен. Проверьте правильность написания или доступ к нему.",
        "no_lib": "🚫 Библиотека `google-generativeai` не установлена. Выполните `.terminal pip install google-generativeai`",
        "no_api_key": "🚫 API ключ для Gemini не установлен. Введите `.config Sy4enishQuotes` и укажите ваш ключ.",
        "generating": "✨ Генерирую парную цитату...",
        "gemini_error": "❌ Ошибка Gemini: {}",
    }

    strings_ru = {
        "name": "Sy4enishQuotes",
        "fetching": "⏳ Загружаю цитату...",
        "no_quotes": "🚫 Не удалось найти подходящие цитаты в канале.",
        "error": "❌ Произошла ошибка: {}",
        "channel_not_found": "🚫 Канал '{}' не найден или недоступен. Проверьте правильность написания или доступ к нему.",
        "no_lib": "🚫 Библиотека `google-generativeai` не установлена. Выполните `.terminal pip install google-generativeai`",
        "no_api_key": "🚫 API ключ для Gemini не установлен. Введите `.config Sy4enishQuotes` и укажите ваш ключ.",
        "generating": "✨ Генерирую парную цитату...",
        "gemini_error": "❌ Ошибка Gemini: {}",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "GEMINI_API_KEY",
                None,
                "API ключ от Google Gemini (получить в Google AI Studio)",
                validator=loader.validators.Hidden(), # Скрытый параметр для безопасности
            ),
            loader.ConfigValue(
                "GEMINI_MODEL",
                "gemini-1.5-flash",
                "Модель Gemini для генерации. Рекомендуется использовать 'gemini-1.5-flash' или 'gemini-1.5-pro'.",
                validator=loader.validators.Choice(["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]),
            ),
        )
        self._client = None
        self._db = None
        self._channel_entity = None # Здесь будет храниться объект канала

    async def client_ready(self, client, db):
        """Инициализация клиента и базы данных при запуске бота."""
        self._client = client
        self._db = db
        try:
            # Получаем сущность канала один раз при старте
            self._channel_entity = await self._client.get_entity(QUOTES_CHANNEL)
            logger.info(f"[{self.strings['name']}] Успешно подключен к каналу @{QUOTES_CHANNEL}")
        except Exception as e:
            logger.error(f"[{self.strings['name']}] Не удалось получить сущность для канала @{QUOTES_CHANNEL}: {e}")
            self._channel_entity = None # Сбрасываем, если произошла ошибка

    @loader.command(
        ru_doc="Кинуть случайную цитату из канала @quotesSy4enish.",
        en_doc="Send a random quote from @quotesSy4enish channel."
    )
    async def pquotecmd(self, message: Message):
        """Отправить случайную цитату из канала."""
        await utils.answer(message, self.strings("fetching"))

        # Повторная попытка получить сущность канала, если она не была получена ранее
        if not self._channel_entity:
            try:
                self._channel_entity = await self._client.get_entity(QUOTES_CHANNEL)
            except Exception:
                logger.exception(f"[{self.strings['name']}] Ошибка при повторной попытке получить сущность канала @{QUOTES_CHANNEL}")
                return await utils.answer(message, self.strings("channel_not_found").format(QUOTES_CHANNEL))

        quotes = []
        try:
            # Итерируем последние сообщения в канале
            async for msg in self._client.iter_messages(self._channel_entity, limit=MESSAGE_POOL_LIMIT):
                if msg.text:
                    # Исключаем сообщения, содержащие ссылки
                    if not re.search(r"https?://\S+|www\.\S+", msg.text):
                        quotes.append(msg.text)
            
            if not quotes:
                return await utils.answer(message, self.strings("no_quotes"))

            # Выбираем случайную цитату и отправляем её
            random_quote = random.choice(quotes)
            await utils.answer(message, random_quote)

        except Exception as e:
            logger.exception(f"[{self.strings['name']}] Произошла ошибка при получении или отправке цитаты.")
            await utils.answer(message, self.strings("error").format(e))

    @loader.command(
        ru_doc="[тема] - Сгенерировать парную цитату через Gemini.\n"
               "Пример: .gpquote любовь",
        en_doc="[topic] - Generate a paired quote via Gemini.\n"
               "Example: .gpquote love"
    )
    async def gpquotecmd(self, message: Message):
        """Сгенерировать парную цитату с помощью Gemini."""
        if genai is None:
            return await utils.answer(message, self.strings("no_lib"))

        api_key = self.config["GEMINI_API_KEY"]
        if not api_key:
            return await utils.answer(message, self.strings("no_api_key"))

        args = utils.get_args_raw(message) # Получаем аргументы команды (тема)
        await utils.answer(message, self.strings("generating"))

        try:
            genai.configure(api_key=api_key)
            model_name = self.config["GEMINI_MODEL"]
            model = genai.GenerativeModel(model_name)
            
            topic_instruction = ""
            if args:
                topic_instruction = f" Тема или контекст цитаты: {args}."

            prompt = (
                f"Сгенерируй одну короткую парную цитату для статусов.{topic_instruction} "
                "Это должны быть строго две короткие фразы, которые дополняют друг друга. "
                "Выведи только текст цитат, без лишних символов, без нумерации и без markdown (символа `). "
                "Фразы должны быть короткими, чтобы не было длинного текста. "
                "Формат вывода:\n"
                "Первая часть\n\n"
                "Вторая часть"
            )

            # Выполняем запрос к Gemini синхронно в отдельном потоке
            response = await utils.run_sync(model.generate_content, prompt)
            
            # Очистка от возможных остаточных символов форматирования (например, backticks)
            text = response.text.replace("`", "").strip()
            
            await utils.answer(message, text)

        except Exception as e:
            logger.exception(f"[{self.strings['name']}] Gemini Error")
            await utils.answer(message, self.strings("gemini_error").format(e))