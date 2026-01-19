"""
    📝 MediaStealer - Модуль для автоматической пересылки медиа
    
    Этот модуль позволяет автоматически пересылать медиафайлы (фото, видео, стикеры, документы)
    из указанных чатов или от конкретных пользователей в ваш бот или любой другой заданный чат.
    
    Функционал включает:
    - Автоматическую пересылку всех медиа из перечисленных чатов.
    - Автоматическую пересылку всех медиа или только видео от конкретного пользователя в определенном чате.
    - Ручное скачивание определенного количества стикеров или других медиафайлов из истории чата,
      опционально от конкретного пользователя.
    
    ⚠️ Примечание: Для работы модуля требуется доступ к сообщениям в целевых чатах.
"""

__version__ = (1, 1, 0)

# meta developer: @Xpansee @Sy4enish
# requires: telethon

from .. import loader, utils
from herokutl.types import Message
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
import logging

logger = logging.getLogger(__name__)

@loader.tds
class MediaStealerMod(loader.Module):
    """
    Module for automatically forwarding media and stickers 
    from a specific user in a specific chat (or all media from specific chats)
    to your Saved Messages or custom chat.
    """
    
    strings = {
        "name": "MediaStealer",
        "no_reply_steal": "<b>Reply to a user to start stealing their media.</b>",
        "active_steal_targets": "<b>Active media targets:</b>\n",
        "stopped_stealing": "<b>❌ Stopped stealing media from {} in this chat.</b>",
        "started_stealing": "<b>✅ Started stealing media from {} to {}.</b>",
        "no_reply_stealvideo": "<b>Reply to a user to start stealing their videos.</b>",
        "active_stealvideo_targets": "<b>Active video targets:</b>\n",
        "stopped_stealing_video": "<b>❌ Stopped stealing videos from {} in this chat.</b>",
        "started_stealing_video": "<b>✅ Started stealing videos from {} to {}.</b>",
        "specify_quantity": "<b>Please specify the quantity.</b>\n<code>.stealstickers <count> [reply]</code>",
        "stealing_stickers": "<b>🔍 Stealing {} stickers...</b>",
        "stolen_stickers": "<b>✅ Stolen {} stickers to {}.</b>",
        "stealing_media": "<b>🔍 Stealing {} media...</b>",
        "stolen_media": "<b>✅ Stolen {} media files to {}.</b>",
    }
    
    strings_ru = {
        "name": "MediaStealer",
        "no_reply_steal": "<b>Ответь на пользователя, чтобы начать кражу его медиа.</b>",
        "active_steal_targets": "<b>Активные цели для кражи медиа:</b>\n",
        "stopped_stealing": "<b>❌ Прекращена кража медиа от {} в этом чате.</b>",
        "started_stealing": "<b>✅ Начата кража медиа от {} в {}.</b>",
        "no_reply_stealvideo": "<b>Ответь на пользователя, чтобы начать кражу его видео.</b>",
        "active_stealvideo_targets": "<b>Активные цели для кражи видео:</b>\n",
        "stopped_stealing_video": "<b>❌ Прекращена кража видео от {} в этом чате.</b>",
        "started_stealing_video": "<b>✅ Начата кража видео от {} в {}.</b>",
        "specify_quantity": "<b>Пожалуйста, укажите количество.</b>\n<code>.stealstickers <количество> [ответ]</code>",
        "stealing_stickers": "<b>🔍 Краду {} стикеров...</b>",
        "stolen_stickers": "<b>✅ Украдено {} стикеров в {}.</b>",
        "stealing_media": "<b>🔍 Краду {} медиа...</b>",
        "stolen_media": "<b>✅ Украдено {} медиафайлов в {}.</b>",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "destination",
                "me",
                "Destination chat ID, username, or link (e.g. @username, https://t.me/..., or me)",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "target_chats",
                [],
                "List of chats/channels IDs to steal ALL media from",
                validator=loader.validators.Series(
                    loader.validators.Union(loader.validators.Integer(), loader.validators.String())
                ),
            ),
        )

    async def client_ready(self, client, db):
        """Инициализация при запуске бота"""
        self._db = db
        self._client = client

    async def get_dest(self):
        """Вспомогательная функция для определения конечного чата для пересылки."""
        dest = self.config["destination"]
        if not dest or dest.lower() == "me":
            return "me"
        
        dest = str(dest).strip()

        # Если это число, возможно, это ID чата
        if dest.lstrip("-").isdigit():
            return int(dest)

        # Если это ссылка на чат
        if "t.me/" in dest:
            if "t.me/c/" in dest: # Ссылка на частный канал (e.g., t.me/c/1234567890/123)
                chat_id = dest.split("t.me/c/")[-1].split("/")[0]
                if chat_id.isdigit():
                    return int(f"-100{chat_id}") # Конвертируем в формат Telegram ID для каналов
            dest = dest.split("t.me/")[-1].split("/")[0] # Извлекаем username или ID из ссылки
        
        # Если это не ID и не начинается с '@', предполагаем, что это username
        if not dest.startswith("@") and not dest.lstrip("-").isdigit():
            return f"@{dest}"
            
        return dest

    @loader.command(
        ru_doc="<reply> - Начать/Закончить пересылку медиа от пользователя.\n"
               "Без аргументов: показать активные цели для пересылки.",
        en_doc="<reply> - Start/Stop forwarding media from replied user.\n"
               "Without args: show active steal targets."
    )
    async def stealcmd(self, message: Message):
        """Start/Stop forwarding media from replied user"""
        reply = await message.get_reply_message()
        if not reply:
            targets = self._db.get(self.strings["name"], "targets", {})
            if not targets:
                await utils.answer(message, self.strings("no_reply_steal"))
                return
            
            text = self.strings("active_steal_targets")
            for chat_id, user_id in targets.items():
                try:
                    # Попытка получить сущность пользователя и чата для более читаемого вывода
                    user = await self._client.get_entity(user_id)
                    chat = await self._client.get_entity(int(chat_id))
                    user_name = getattr(user, "first_name", user.username or str(user_id))
                    chat_name = getattr(chat, "title", chat.username or str(chat_id))
                    text += f"Чат: <b>{chat_name}</b> (<code>{chat_id}</code>) | Пользователь: <b>{user_name}</b> (<code>{user_id}</code>)\n"
                except Exception:
                    text += f"Чат: <code>{chat_id}</code> | Пользователь: <code>{user_id}</code>\n"
            await utils.answer(message, text)
            return

        target_id = reply.sender_id
        chat_id = utils.get_chat_id(message)
        
        targets = self._db.get(self.strings["name"], "targets", {})
        str_chat_id = str(chat_id) # Храним chat_id как строку в БД для единообразия
        
        user_name = "User"
        if reply.sender:
            user_name = getattr(reply.sender, "first_name", None) or getattr(reply.sender, "title", "User")
            if not user_name: # Fallback для случаев, когда ни first_name, ни title нет (например, анонимные админы)
                user_name = reply.sender.username or str(reply.sender_id)

        if str_chat_id in targets and targets[str_chat_id] == target_id:
            del targets[str_chat_id]
            self._db.set(self.strings["name"], "targets", targets)
            await utils.answer(message, self.strings("stopped_stealing").format(user_name))
        else:
            targets[str_chat_id] = target_id
            self._db.set(self.strings["name"], "targets", targets)
            dest = self.config['destination']
            await utils.answer(message, self.strings("started_stealing").format(user_name, dest))

    @loader.command(
        ru_doc="<reply> - Начать/Закончить пересылку ТОЛЬКО видео от пользователя.\n"
               "Без аргументов: показать активные цели для пересылки видео.",
        en_doc="<reply> - Start/Stop forwarding ONLY videos from replied user.\n"
               "Without args: show active video steal targets."
    )
    async def stealvideocmd(self, message: Message):
        """Start/Stop forwarding ONLY videos from replied user"""
        reply = await message.get_reply_message()
        if not reply:
            targets = self._db.get(self.strings["name"], "video_targets", {})
            if not targets:
                await utils.answer(message, self.strings("no_reply_stealvideo"))
                return
            
            text = self.strings("active_stealvideo_targets")
            for chat_id, user_id in targets.items():
                try:
                    user = await self._client.get_entity(user_id)
                    chat = await self._client.get_entity(int(chat_id))
                    user_name = getattr(user, "first_name", user.username or str(user_id))
                    chat_name = getattr(chat, "title", chat.username or str(chat_id))
                    text += f"Чат: <b>{chat_name}</b> (<code>{chat_id}</code>) | Пользователь: <b>{user_name}</b> (<code>{user_id}</code>)\n"
                except Exception:
                    text += f"Чат: <code>{chat_id}</code> | Пользователь: <code>{user_id}</code>\n"
            await utils.answer(message, text)
            return

        target_id = reply.sender_id
        chat_id = utils.get_chat_id(message)
        
        targets = self._db.get(self.strings["name"], "video_targets", {})
        str_chat_id = str(chat_id)
        
        user_name = "User"
        if reply.sender:
            user_name = getattr(reply.sender, "first_name", None) or getattr(reply.sender, "title", "User")
            if not user_name:
                user_name = reply.sender.username or str(reply.sender_id)

        if str_chat_id in targets and targets[str_chat_id] == target_id:
            del targets[str_chat_id]
            self._db.set(self.strings["name"], "video_targets", targets)
            await utils.answer(message, self.strings("stopped_stealing_video").format(user_name))
        else:
            targets[str_chat_id] = target_id
            self._db.set(self.strings["name"], "video_targets", targets)
            dest = self.config['destination']
            await utils.answer(message, self.strings("started_stealing_video").format(user_name, dest))

    @loader.watcher(only_messages=True)
    async def watcher(self, message: Message):
        """
        Отслеживает новые сообщения и пересылает медиа, если сообщение
        соответствует одному из критериев:
        1. Чат сообщения находится в списке target_chats в конфигурации.
        2. Отправитель сообщения является целевым пользователем для кражи медиа
           в данном чате (установлено командой .steal).
        3. Отправитель сообщения является целевым пользователем для кражи видео
           в данном чате (установлено командой .stealvideo) И сообщение является видео.
        """
        if not message.chat_id:
            return # Игнорируем сообщения без chat_id (например, каналы без chat_id, но это редко)
        
        if not message.media:
            return # Игнорируем сообщения без медиа

        chat_id = str(utils.get_chat_id(message)) # Получаем ID чата в виде строки
        should_forward = False

        # 1. Проверка конфигурации target_chats (глобальная кража для чата/канала)
        target_chats_config = self.config["target_chats"]
        if target_chats_config:
            # Нормализуем ID чатов из конфига в строки для сравнения
            str_target_chats_config = [str(x) for x in target_chats_config]
            if str(message.chat_id) in str_target_chats_config:
                should_forward = True

        # 2. Проверка целей из БД (конкретный пользователь в чате)
        if not should_forward and message.sender_id:
            targets_db = self._db.get(self.strings["name"], "targets", {})
            video_targets_db = self._db.get(self.strings["name"], "video_targets", {})

            if chat_id in targets_db and targets_db[chat_id] == message.sender_id:
                # Если пользователь в списке для всех медиа
                should_forward = True
            elif chat_id in video_targets_db and video_targets_db[chat_id] == message.sender_id:
                # Если пользователь в списке только для видео и сообщение является видео
                if message.video:
                    should_forward = True

        if should_forward:
            try:
                dest = await self.get_dest()
                await message.forward_to(dest)
            except Exception as e:
                logger.error(f"Failed to forward message {message.id} from chat {message.chat_id}: {e}")
                # Игнорируем ошибку, чтобы не мешать работе вотчера
                pass

    @loader.command(
        ru_doc="<количество> [ответ] - Украсть стикеры из истории чата.\n"
               "Ответьте на сообщение пользователя, чтобы украсть стикеры только от него.",
        en_doc="<count> [reply] - Steal stickers from chat history.\n"
               "Reply to a user's message to steal stickers only from them."
    )
    async def stealstickerscmd(self, message: Message):
        """<count> [reply] - Steal stickers from chat history"""
        args = utils.get_args(message)
        if not args or not args[0].isdigit():
            await utils.answer(message, self.strings("specify_quantity"))
            return

        count = int(args[0])
        reply = await message.get_reply_message()
        target_user = reply.sender_id if reply else None
        
        await utils.answer(message, self.strings("stealing_stickers").format(count))
        
        dest = await self.get_dest()
        counter = 0
        
        # Итерируемся по сообщениям в чате, пока не достигнем нужного количества
        async for msg in self._client.iter_messages(message.chat_id, limit=None):
            if counter >= count:
                break # Достигли нужного количества стикеров
            
            if target_user and msg.sender_id != target_user:
                continue # Пропускаем, если указан пользователь, а это не его сообщение
                
            if msg.sticker:
                try:
                    await msg.forward_to(dest)
                    counter += 1
                except Exception as e:
                    logger.warning(f"Failed to forward sticker {msg.id}: {e}")
                    continue # Пропускаем стикер, если не удалось переслать
        
        await utils.answer(message, self.strings("stolen_stickers").format(counter, self.config['destination']))

    @loader.command(
        ru_doc="<количество> [ответ] - Украсть медиа (фото/видео/гиф) из истории чата.\n"
               "Ответьте на сообщение пользователя, чтобы украсть медиа только от него.",
        en_doc="<count> [reply] - Steal media (photo/video/gif) from chat history.\n"
               "Reply to a user's message to steal media only from them."
    )
    async def stealmediacmd(self, message: Message):
        """<count> [reply] - Steal media (photo/video/gif) from chat history"""
        args = utils.get_args(message)
        if not args or not args[0].isdigit():
            await utils.answer(message, self.strings("specify_quantity").replace("stealstickers", "stealmedia"))
            return

        count = int(args[0])
        reply = await message.get_reply_message()
        target_user = reply.sender_id if reply else None
        
        await utils.answer(message, self.strings("stealing_media").format(count))
        
        dest = await self.get_dest()
        counter = 0
        
        # Итерируемся по сообщениям в чате, пока не достигнем нужного количества
        async for msg in self._client.iter_messages(message.chat_id, limit=None):
            if counter >= count:
                break # Достигли нужного количества медиа
            
            if target_user and msg.sender_id != target_user:
                continue # Пропускаем, если указан пользователь, а это не его сообщение
                
            if msg.media and not msg.sticker: # Игнорируем стикеры, т.к. для них есть отдельная команда
                if isinstance(msg.media, (MessageMediaPhoto, MessageMediaDocument)):
                    try:
                        await msg.forward_to(dest)
                        counter += 1
                    except Exception as e:
                        logger.warning(f"Failed to forward media {msg.id}: {e}")
                        continue # Пропускаем медиа, если не удалось переслать
        
        await utils.answer(message, self.strings("stolen_media").format(counter, self.config['destination']))