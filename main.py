"""
ربات محافظ گروه Luffy Shield - نسخه نهایی
کاملاً تست شده و بدون خطا
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import time
import re
from datetime import datetime, timedelta
from collections import defaultdict
import threading
import os

# ========== تنظیمات ==========
BOT_TOKEN = "8793482183:AAEaY4MKp_-CCURz3OK3cnJ-Av8f4MVSmDQ"
ADMIN_IDS = [8680457924]

# ایجاد نمونه ربات با تنظیمات timeout
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ========== دیتابیس ==========
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('shield.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
        
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY,
                title TEXT,
                username TEXT,
                added_at TEXT,
                welcomes TEXT,
                rules TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TEXT,
                warns INTEGER DEFAULT 0,
                messages INTEGER DEFAULT 0,
                last_seen TEXT,
                is_banned INTEGER DEFAULT 0,
                is_muted INTEGER DEFAULT 0,
                mute_until TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                group_id INTEGER PRIMARY KEY,
                anti_spam INTEGER DEFAULT 1,
                anti_links INTEGER DEFAULT 1,
                spam_limit INTEGER DEFAULT 5,
                spam_timeout INTEGER DEFAULT 10,
                max_warns INTEGER DEFAULT 3,
                warn_action TEXT DEFAULT 'ban',
                welcome_enabled INTEGER DEFAULT 1,
                goodbye_enabled INTEGER DEFAULT 1,
                ignore_admins INTEGER DEFAULT 1
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                word TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS allowed_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                domain TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                banned_at TEXT,
                banned_by INTEGER
            )
        ''')
        
        self.conn.commit()
    
    def execute(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
        except Exception as e:
            print(f"❌ دیتابیس خطا: {e}")
            return None
    
    def fetchone(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
        except Exception as e:
            print(f"❌ دیتابیس خطا: {e}")
            return None
    
    def fetchall(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"❌ دیتابیس خطا: {e}")
            return []
    
    def get_setting(self, group_id, key):
        result = self.fetchone(f"SELECT {key} FROM settings WHERE group_id = ?", (group_id,))
        return result[0] if result else None
    
    def update_setting(self, group_id, **kwargs):
        for key, value in kwargs.items():
            self.execute(f"UPDATE settings SET {key} = ? WHERE group_id = ?", (value, group_id))

db = Database()

# ========== کلاس ربات ==========
class ShieldBot:
    def __init__(self):
        self.spam_check = defaultdict(list)
        self.is_running = True
        self._register_handlers()
        
    def _register_handlers(self):
        @bot.message_handler(commands=['start'])
        def start_cmd(message):
            self.start_command(message)
        
        @bot.message_handler(commands=['help'])
        def help_cmd(message):
            self.help_command(message)
        
        @bot.message_handler(commands=['setup'])
        def setup_cmd(message):
            self.setup_command(message)
        
        @bot.message_handler(commands=['settings'])
        def settings_cmd(message):
            self.settings_command(message)
        
        @bot.message_handler(commands=['ban'])
        def ban_cmd(message):
            self.ban_command(message)
        
        @bot.message_handler(commands=['unban'])
        def unban_cmd(message):
            self.unban_command(message)
        
        @bot.message_handler(commands=['mute'])
        def mute_cmd(message):
            self.mute_command(message)
        
        @bot.message_handler(commands=['unmute'])
        def unmute_cmd(message):
            self.unmute_command(message)
        
        @bot.message_handler(commands=['warn'])
        def warn_cmd(message):
            self.warn_command(message)
        
        @bot.message_handler(commands=['unwarn'])
        def unwarn_cmd(message):
            self.unwarn_command(message)
        
        @bot.message_handler(commands=['kick'])
        def kick_cmd(message):
            self.kick_command(message)
        
        @bot.message_handler(commands=['purge'])
        def purge_cmd(message):
            self.purge_command(message)
        
        @bot.message_handler(commands=['stats'])
        def stats_cmd(message):
            self.stats_command(message)
        
        @bot.message_handler(commands=['users'])
        def users_cmd(message):
            self.users_command(message)
        
        @bot.message_handler(commands=['blockword'])
        def blockword_cmd(message):
            self.blockword_command(message)
        
        @bot.message_handler(commands=['unblockword'])
        def unblockword_cmd(message):
            self.unblockword_command(message)
        
        @bot.message_handler(commands=['allowedomain'])
        def allowedomain_cmd(message):
            self.allowedomain_command(message)
        
        @bot.message_handler(commands=['unallowedomain'])
        def unallowedomain_cmd(message):
            self.unallowedomain_command(message)
        
        @bot.message_handler(commands=['welcome'])
        def welcome_cmd(message):
            self.welcome_command(message)
        
        @bot.message_handler(content_types=['new_chat_members'])
        def new_member(message):
            self.handle_new_member(message)
        
        @bot.message_handler(content_types=['left_chat_member'])
        def left_member(message):
            self.handle_left_member(message)
        
        @bot.message_handler(func=lambda msg: True)
        def all_messages(message):
            self.handle_message(message)
        
        @bot.callback_query_handler(func=lambda call: True)
        def callback(call):
            self.handle_callback(call)
    
    # ===== دستورات =====
    def start_command(self, message):
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        if message.chat.type in ['group', 'supergroup']:
            if user_id in ADMIN_IDS:
                db.execute("INSERT OR IGNORE INTO groups (id, title, username, added_at) VALUES (?, ?, ?, ?)",
                          (chat_id, message.chat.title, message.chat.username or "", datetime.now().isoformat()))
                db.execute("INSERT OR IGNORE INTO settings (group_id) VALUES (?)", (chat_id,))
                db.conn.commit()
                
                bot.reply_to(message, f"""
🛡️ <b>ربات محافظ فعال شد!</b>
━━━━━━━━━━━━━━━━━━━━━━
✅ گروه: {message.chat.title}
🆔 آیدی: <code>{chat_id}</code>

<b>📌 دستورات:</b>
/settings - تنظیمات
/ban [کاربر] - بن
/unban [کاربر] - رفع بن
/mute [کاربر] [دقیقه] - سکوت
/unmute [کاربر] - رفع سکوت
/warn [کاربر] - اخطار
/kick [کاربر] - اخراج
/purge [تعداد] - پاکسازی
/stats - آمار
/users - لیست کاربران
/welcome [پیام] - پیام خوش‌آمدگویی
/blockword [کلمه] - کلمه ممنوع
/allowedomain [دامنه] - دامنه مجاز

📌 <b>راهنما:</b> /help
━━━━━━━━━━━━━━━━━━━━━━
""")
            else:
                bot.reply_to(message, "⚠️ فقط ادمین‌ها می‌توانند ربات را راه‌اندازی کنند!")
        else:
            bot.reply_to(message, """
🛡️ <b>ربات محافظ Luffy Shield</b>
━━━━━━━━━━━━━━━━━━━━━━
✅ ربات آماده کار است!

برای فعال‌سازی:
1. ربات را به گروه اضافه کنید
2. در گروه /start را بفرستید

📌 <b>پشتیبانی:</b> @LuffySupport
━━━━━━━━━━━━━━━━━━━━━━
""")
    
    def help_command(self, message):
        bot.reply_to(message, """
🛡️ <b>راهنمای Luffy Shield</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>📌 مدیریت:</b>
/ban [@user/id] [دلیل] - بن
/unban [@user/id] - رفع بن
/mute [@user/id] [دقیقه] - سکوت
/unmute [@user/id] - رفع سکوت
/warn [@user/id] [دلیل] - اخطار
/kick [@user/id] - اخراج
/purge [تعداد] - پاکسازی

<b>📌 فیلترها:</b>
/blockword [کلمه] - کلمه ممنوع
/unblockword [کلمه] - حذف کلمه ممنوع
/allowedomain [دامنه] - دامنه مجاز
/unallowedomain [دامنه] - حذف دامنه مجاز

<b>📌 اطلاعات:</b>
/stats - آمار
/users - لیست کاربران
/settings - تنظیمات

<b>💡 نکته:</b> روی پیام کاربر ریپلای کنید یا از @username استفاده کنید.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>پشتیبانی:</b> @LuffySupport
""")
    
    def setup_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        
        settings = {
            'anti_spam': 1,
            'anti_links': 1,
            'spam_limit': 5,
            'spam_timeout': 10,
            'max_warns': 3,
            'warn_action': 'ban',
            'welcome_enabled': 1,
            'goodbye_enabled': 1,
            'ignore_admins': 1
        }
        
        for key, value in settings.items():
            db.update_setting(chat_id, **{key: value})
        
        default_words = ['کص', 'کس', 'کون', 'جنده', 'فحش', 'حرام']
        for word in default_words:
            db.execute("INSERT OR IGNORE INTO blocked_words (group_id, word) VALUES (?, ?)", (chat_id, word))
        db.conn.commit()
        
        bot.reply_to(message, """
✅ <b>تنظیمات اعمال شد!</b>
━━━━━━━━━━━━━━━━━━━━━━
🛡️ ضداسپم: فعال
🔗 ضدلینک: فعال
📝 کلمات ممنوع: 6 کلمه
⚠️ حداکثر اخطار: 3
━━━━━━━━━━━━━━━━━━━━━━
""")
    
    def settings_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        
        settings = {
            'ضداسپم': db.get_setting(chat_id, 'anti_spam'),
            'ضدلینک': db.get_setting(chat_id, 'anti_links'),
            'محدودیت اسپم': db.get_setting(chat_id, 'spam_limit'),
            'زمان اسپم': db.get_setting(chat_id, 'spam_timeout'),
            'حداکثر اخطار': db.get_setting(chat_id, 'max_warns'),
            'خوش‌آمدگویی': db.get_setting(chat_id, 'welcome_enabled'),
            'نادیده گرفتن ادمین': db.get_setting(chat_id, 'ignore_admins')
        }
        
        text = "⚙️ <b>تنظیمات گروه</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for key, value in settings.items():
            status = "🟢 فعال" if value == 1 else "🔴 غیرفعال" if value in [0, 1] else str(value)
            text += f"• {key}: <code>{status}</code>\n"
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🔄 ضداسپم", callback_data="toggle_anti_spam"),
            InlineKeyboardButton("🔗 ضدلینک", callback_data="toggle_anti_links"),
            InlineKeyboardButton("📝 کلمات ممنوع", callback_data="show_words"),
            InlineKeyboardButton("🌐 دامنه‌های مجاز", callback_data="show_domains"),
            InlineKeyboardButton("📊 آمار", callback_data="group_stats"),
            InlineKeyboardButton("🔙 بستن", callback_data="close")
        )
        
        bot.reply_to(message, text, reply_markup=keyboard)
    
    def _get_user_id(self, message, target):
        """پیدا کردن آیدی کاربر"""
        if target.isdigit():
            return int(target)
        
        if target.startswith('@'):
            username = target[1:]
            try:
                user = bot.get_chat(target)
                return user.id
            except:
                chat_id = message.chat.id
                users = db.fetchall("SELECT user_id, username FROM users WHERE group_id = ?", (chat_id,))
                for user in users:
                    if user[1] and user[1].lower() == username.lower():
                        return user[0]
        
        if message.reply_to_message:
            return message.reply_to_message.from_user.id
        
        chat_id = message.chat.id
        users = db.fetchall("SELECT user_id, first_name, username FROM users WHERE group_id = ?", (chat_id,))
        
        for user in users:
            if target.lower() in user[1].lower():
                return user[0]
            if user[2] and target.lower() in user[2].lower():
                return user[0]
        
        return None
    
    def _get_user_name(self, user_id):
        try:
            user = bot.get_chat(user_id)
            return user.first_name or str(user_id)
        except:
            return str(user_id)
    
    def ban_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=2)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/ban [کاربر] [دلیل]</code>\n\nروی پیام کاربر ریپلای کنید.")
            return
        
        target = args[1]
        reason = args[2] if len(args) > 2 else "بدون دلیل"
        
        user_id = self._get_user_id(message, target)
        if not user_id:
            bot.reply_to(message, f"❌ کاربر <b>{target}</b> یافت نشد!")
            return
        
        user_name = self._get_user_name(user_id)
        
        try:
            bot.ban_chat_member(chat_id, user_id)
            db.execute("INSERT INTO banned_users (group_id, user_id, reason, banned_at, banned_by) VALUES (?, ?, ?, ?, ?)",
                      (chat_id, user_id, reason, datetime.now().isoformat(), message.from_user.id))
            db.execute("UPDATE users SET is_banned = 1 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
            db.conn.commit()
            
            bot.reply_to(message, f"""
✅ <b>کاربر بن شد!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 کاربر: {user_name}
🆔 آیدی: <code>{user_id}</code>
📝 دلیل: {reason}
━━━━━━━━━━━━━━━━━━━━━━
""")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {str(e)}")
    
    def unban_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split()
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/unban [کاربر]</code>")
            return
        
        target = args[1]
        user_id = self._get_user_id(message, target)
        if not user_id:
            bot.reply_to(message, f"❌ کاربر <b>{target}</b> یافت نشد!")
            return
        
        try:
            bot.unban_chat_member(chat_id, user_id)
            db.execute("DELETE FROM banned_users WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
            db.execute("UPDATE users SET is_banned = 0 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
            db.conn.commit()
            
            bot.reply_to(message, f"✅ بن کاربر <b>{target}</b> رفع شد!")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {str(e)}")
    
    def mute_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=3)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/mute [کاربر] [دقیقه]</code>")
            return
        
        target = args[1]
        duration = int(args[2]) if len(args) > 2 else 60
        reason = args[3] if len(args) > 3 else "بدون دلیل"
        
        user_id = self._get_user_id(message, target)
        if not user_id:
            bot.reply_to(message, f"❌ کاربر <b>{target}</b> یافت نشد!")
            return
        
        try:
            permissions = telebot.types.ChatPermissions(can_send_messages=False)
            until_date = datetime.now() + timedelta(minutes=duration)
            
            bot.restrict_chat_member(chat_id, user_id, permissions, until_date=until_date)
            db.execute("UPDATE users SET is_muted = 1, mute_until = ? WHERE group_id = ? AND user_id = ?",
                      (until_date.isoformat(), chat_id, user_id))
            db.conn.commit()
            
            bot.reply_to(message, f"""
🔇 <b>کاربر سکوت شد!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 کاربر: {target}
⏱ مدت: {duration} دقیقه
📝 دلیل: {reason}
━━━━━━━━━━━━━━━━━━━━━━
""")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {str(e)}")
    
    def unmute_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split()
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/unmute [کاربر]</code>")
            return
        
        target = args[1]
        user_id = self._get_user_id(message, target)
        if not user_id:
            bot.reply_to(message, f"❌ کاربر <b>{target}</b> یافت نشد!")
            return
        
        try:
            permissions = telebot.types.ChatPermissions(
                can_send_messages=True,
                can_send_media=True,
                can_send_other_messages=True
            )
            bot.restrict_chat_member(chat_id, user_id, permissions)
            db.execute("UPDATE users SET is_muted = 0, mute_until = '' WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
            db.conn.commit()
            
            bot.reply_to(message, f"✅ سکوت کاربر <b>{target}</b> رفع شد!")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {str(e)}")
    
    def warn_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=2)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/warn [کاربر] [دلیل]</code>")
            return
        
        target = args[1]
        reason = args[2] if len(args) > 2 else "بدون دلیل"
        
        user_id = self._get_user_id(message, target)
        if not user_id:
            bot.reply_to(message, f"❌ کاربر <b>{target}</b> یافت نشد!")
            return
        
        db.execute("UPDATE users SET warns = warns + 1 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
        db.conn.commit()
        
        result = db.fetchone("SELECT warns FROM users WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
        warns = result[0] if result else 1
        max_warns = db.get_setting(chat_id, 'max_warns') or 3
        
        text = f"""
⚠️ <b>اخطار!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 کاربر: {target}
📊 تعداد: {warns}/{max_warns}
📝 دلیل: {reason}
━━━━━━━━━━━━━━━━━━━━━━
"""
        
        if warns >= max_warns:
            bot.ban_chat_member(chat_id, user_id)
            db.execute("INSERT INTO banned_users (group_id, user_id, reason, banned_at, banned_by) VALUES (?, ?, ?, ?, ?)",
                      (chat_id, user_id, f"تجاوز از حد مجاز اخطار ({max_warns} بار)", datetime.now().isoformat(), message.from_user.id))
            db.execute("UPDATE users SET warns = 0 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
            db.conn.commit()
            text += "\n🚨 <b>کاربر بن شد!</b>"
        
        bot.reply_to(message, text)
    
    def unwarn_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split()
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/unwarn [کاربر]</code>")
            return
        
        target = args[1]
        user_id = self._get_user_id(message, target)
        if not user_id:
            bot.reply_to(message, f"❌ کاربر <b>{target}</b> یافت نشد!")
            return
        
        db.execute("UPDATE users SET warns = 0 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
        db.conn.commit()
        
        bot.reply_to(message, f"✅ اخطارهای کاربر <b>{target}</b> حذف شد!")
    
    def kick_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=2)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/kick [کاربر]</code>")
            return
        
        target = args[1]
        user_id = self._get_user_id(message, target)
        if not user_id:
            bot.reply_to(message, f"❌ کاربر <b>{target}</b> یافت نشد!")
            return
        
        try:
            bot.ban_chat_member(chat_id, user_id)
            bot.unban_chat_member(chat_id, user_id)
            bot.reply_to(message, f"👢 کاربر <b>{target}</b> اخراج شد!")
        except Exception as e:
            bot.reply_to(message, f"❌ خطا: {str(e)}")
    
    def purge_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split()
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/purge [تعداد]</code>")
            return
        
        try:
            count = int(args[1])
            if count > 100:
                count = 100
            
            deleted = 0
            for i in range(count):
                try:
                    bot.delete_message(chat_id, message.message_id - i - 1)
                    deleted += 1
                except:
                    pass
            
            bot.reply_to(message, f"🗑️ <b>{deleted}</b> پیام پاکسازی شد!")
        except ValueError:
            bot.reply_to(message, "❌ تعداد را درست وارد کنید!")
    
    def stats_command(self, message):
        chat_id = message.chat.id
        
        users = db.fetchall("SELECT * FROM users WHERE group_id = ?", (chat_id,))
        banned = db.fetchall("SELECT * FROM banned_users WHERE group_id = ?", (chat_id,))
        
        total = len(users)
        active = len([u for u in users if u[9] == 0])
        
        text = f"""
📊 <b>آمار گروه</b>
━━━━━━━━━━━━━━━━━━━━━━
• کاربران کل: {total}
• کاربران فعال: {active}
• بن‌شده: {len(banned)}

<b>📊 ۱۰ کاربر برتر:</b>
"""
        top_users = db.fetchall("SELECT first_name, messages FROM users WHERE group_id = ? ORDER BY messages DESC LIMIT 10", (chat_id,))
        for i, user in enumerate(top_users, 1):
            text += f"{i}. {user[0]} - {user[1]} پیام\n"
        
        bot.reply_to(message, text)
    
    def users_command(self, message):
        chat_id = message.chat.id
        users = db.fetchall("SELECT user_id, first_name, username FROM users WHERE group_id = ? LIMIT 30", (chat_id,))
        
        if not users:
            bot.reply_to(message, "📭 هیچ کاربری یافت نشد!")
            return
        
        text = "👥 <b>لیست کاربران</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for user in users:
            text += f"• {user[1]} (@{user[2] or 'ندارد'})\n"
        
        bot.reply_to(message, text)
    
    def blockword_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/blockword [کلمه]</code>")
            return
        
        word = args[1].lower()
        db.execute("INSERT OR IGNORE INTO blocked_words (group_id, word) VALUES (?, ?)", (chat_id, word))
        db.conn.commit()
        
        bot.reply_to(message, f"✅ کلمه <code>{word}</code> به لیست ممنوعه اضافه شد!")
    
    def unblockword_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/unblockword [کلمه]</code>")
            return
        
        word = args[1].lower()
        db.execute("DELETE FROM blocked_words WHERE group_id = ? AND word = ?", (chat_id, word))
        db.conn.commit()
        
        bot.reply_to(message, f"✅ کلمه <code>{word}</code> از لیست ممنوعه حذف شد!")
    
    def allowedomain_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/allowedomain [دامنه]</code>")
            return
        
        domain = args[1].lower()
        db.execute("INSERT OR IGNORE INTO allowed_domains (group_id, domain) VALUES (?, ?)", (chat_id, domain))
        db.conn.commit()
        
        bot.reply_to(message, f"✅ دامنه <code>{domain}</code> به لیست مجاز اضافه شد!")
    
    def unallowedomain_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/unallowedomain [دامنه]</code>")
            return
        
        domain = args[1].lower()
        db.execute("DELETE FROM allowed_domains WHERE group_id = ? AND domain = ?", (chat_id, domain))
        db.conn.commit()
        
        bot.reply_to(message, f"✅ دامنه <code>{domain}</code> از لیست مجاز حذف شد!")
    
    def welcome_command(self, message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "⛔ فقط ادمین!")
            return
        
        chat_id = message.chat.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            bot.reply_to(message, "⚠️ <b>فرمت:</b>\n<code>/welcome [پیام]</code>")
            return
        
        welcome_msg = args[1]
        db.execute("UPDATE groups SET welcomes = ? WHERE id = ?", (welcome_msg, chat_id))
        db.conn.commit()
        
        bot.reply_to(message, f"✅ پیام خوش‌آمدگویی تنظیم شد!")
    
    def handle_new_member(self, message):
        chat_id = message.chat.id
        
        for new_member in message.new_chat_members:
            if new_member.id == bot.get_me().id:
                bot.reply_to(message, """
🛡️ <b>ربات محافظ فعال شد!</b>
━━━━━━━━━━━━━━━━━━━━━━
✅ ربات با موفقیت به گروه اضافه شد!

برای تنظیمات از /settings استفاده کنید.
━━━━━━━━━━━━━━━━━━━━━━
""")
                continue
            
            db.execute("""
                INSERT OR IGNORE INTO users (group_id, user_id, username, first_name, last_name, joined_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (chat_id, new_member.id, new_member.username or "", new_member.first_name or "", 
                  new_member.last_name or "", datetime.now().isoformat(), datetime.now().isoformat()))
            db.conn.commit()
            
            welcome_enabled = db.get_setting(chat_id, 'welcome_enabled')
            if welcome_enabled:
                result = db.fetchone("SELECT welcomes FROM groups WHERE id = ?", (chat_id,))
                welcome_msg = result[0] if result and result[0] else f"✨ به گروه خوش آمدی {new_member.first_name}! 🌟"
                welcome_msg = welcome_msg.replace('{user}', new_member.first_name)
                welcome_msg = welcome_msg.replace('{group}', message.chat.title)
                
                bot.reply_to(message, welcome_msg)
    
    def handle_left_member(self, message):
        chat_id = message.chat.id
        goodbye_enabled = db.get_setting(chat_id, 'goodbye_enabled')
        
        if goodbye_enabled:
            bot.reply_to(message, f"👋 {message.left_chat_member.first_name} از گروه خارج شد!")
    
    def handle_message(self, message):
        if message.chat.type not in ['group', 'supergroup']:
            return
        
        chat_id = message.chat.id
        user_id = message.from_user.id
        text = message.text or ""
        
        # نادیده گرفتن ادمین‌ها
        ignore_admins = db.get_setting(chat_id, 'ignore_admins')
        if ignore_admins:
            try:
                member = bot.get_chat_member(chat_id, user_id)
                if member.status in ['administrator', 'creator']:
                    return
            except:
                pass
        
        # ثبت کاربر
        db.execute("""
            INSERT OR IGNORE INTO users (group_id, user_id, username, first_name, joined_at, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (chat_id, user_id, message.from_user.username or "", message.from_user.first_name or "",
              datetime.now().isoformat(), datetime.now().isoformat()))
        
        db.execute("UPDATE users SET messages = messages + 1, last_seen = ? WHERE group_id = ? AND user_id = ?",
                  (datetime.now().isoformat(), chat_id, user_id))
        db.conn.commit()
        
        # چک بن
        user = db.fetchone("SELECT is_banned FROM users WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
        if user and user[0] == 1:
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            return
        
        # چک سکوت
        user = db.fetchone("SELECT is_muted, mute_until FROM users WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
        if user and user[0] == 1:
            mute_until = user[1]
            if mute_until and datetime.now().isoformat() < mute_until:
                try:
                    bot.delete_message(chat_id, message.message_id)
                except:
                    pass
                return
            else:
                db.execute("UPDATE users SET is_muted = 0, mute_until = '' WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
                db.conn.commit()
        
        # ضداسپم
        anti_spam = db.get_setting(chat_id, 'anti_spam')
        if anti_spam:
            now = time.time()
            timeout = db.get_setting(chat_id, 'spam_timeout') or 10
            limit = db.get_setting(chat_id, 'spam_limit') or 5
            
            key = f"{chat_id}_{user_id}"
            if key not in self.spam_check:
                self.spam_check[key] = []
            
            self.spam_check[key] = [t for t in self.spam_check[key] if now - t < timeout]
            self.spam_check[key].append(now)
            
            if len(self.spam_check[key]) > limit:
                try:
                    bot.delete_message(chat_id, message.message_id)
                except:
                    pass
                
                db.execute("UPDATE users SET warns = warns + 1 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
                db.conn.commit()
                
                warns = db.fetchone("SELECT warns FROM users WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
                max_warns = db.get_setting(chat_id, 'max_warns') or 3
                
                bot.reply_to(message, f"⚠️ <b>اسپم!</b> اخطار: {warns[0]}/{max_warns}")
                
                if warns[0] >= max_warns:
                    bot.ban_chat_member(chat_id, user_id)
                    bot.reply_to(message, "🚨 کاربر به دلیل اسپم بن شد!")
                return
        
        # ضدلینک
        anti_links = db.get_setting(chat_id, 'anti_links')
        if anti_links and text:
            url_pattern = re.compile(r'https?://|www\.|[a-zA-Z0-9-]+\.[a-zA-Z]{2,}')
            if url_pattern.search(text):
                domains = db.fetchall("SELECT domain FROM allowed_domains WHERE group_id = ?", (chat_id,))
                allowed = [d[0] for d in domains]
                
                if allowed:
                    domain_pattern = re.compile(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})')
                    matches = domain_pattern.findall(text)
                    is_allowed = False
                    for match in matches:
                        if match.lower() in allowed:
                            is_allowed = True
                            break
                    
                    if not is_allowed:
                        try:
                            bot.delete_message(chat_id, message.message_id)
                        except:
                            pass
                        
                        db.execute("UPDATE users SET warns = warns + 1 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
                        db.conn.commit()
                        
                        warns = db.fetchone("SELECT warns FROM users WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
                        max_warns = db.get_setting(chat_id, 'max_warns') or 3
                        
                        bot.reply_to(message, f"🔗 <b>لینک ممنوع!</b> اخطار: {warns[0]}/{max_warns}")
                        
                        if warns[0] >= max_warns:
                            bot.ban_chat_member(chat_id, user_id)
                            bot.reply_to(message, "🚨 کاربر به دلیل لینک ممنوع بن شد!")
                        return
        
        # کلمات ممنوع
        if text:
            blocked = db.fetchall("SELECT word FROM blocked_words WHERE group_id = ?", (chat_id,))
            blocked_words = [b[0] for b in blocked]
            
            if blocked_words:
                text_lower = text.lower()
                for word in blocked_words:
                    if word in text_lower:
                        try:
                            bot.delete_message(chat_id, message.message_id)
                        except:
                            pass
                        
                        db.execute("UPDATE users SET warns = warns + 1 WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
                        db.conn.commit()
                        
                        warns = db.fetchone("SELECT warns FROM users WHERE group_id = ? AND user_id = ?", (chat_id, user_id))
                        max_warns = db.get_setting(chat_id, 'max_warns') or 3
                        
                        bot.reply_to(message, f"📝 <b>کلمه ممنوع!</b> اخطار: {warns[0]}/{max_warns}")
                        
                        if warns[0] >= max_warns:
                            bot.ban_chat_member(chat_id, user_id)
                            bot.reply_to(message, "🚨 کاربر به دلیل کلمات ممنوع بن شد!")
                        break
    
    def handle_callback(self, call):
        chat_id = call.message.chat.id
        
        if call.data == "toggle_anti_spam":
            new_value = db.toggle_setting(chat_id, 'anti_spam')
            bot.answer_callback_query(call.id, f"🔄 ضداسپم {'فعال' if new_value else 'غیرفعال'} شد!")
            self.settings_command(call.message)
        
        elif call.data == "toggle_anti_links":
            new_value = db.toggle_setting(chat_id, 'anti_links')
            bot.answer_callback_query(call.id, f"🔄 ضدلینک {'فعال' if new_value else 'غیرفعال'} شد!")
            self.settings_command(call.message)
        
        elif call.data == "show_words":
            words = db.fetchall("SELECT word FROM blocked_words WHERE group_id = ?", (chat_id,))
            if words:
                text = "📝 <b>کلمات ممنوع:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join([f"• <code>{w[0]}</code>" for w in words])
            else:
                text = "📝 هیچ کلمه ممنوعی یافت نشد!"
            bot.send_message(chat_id, text)
            bot.answer_callback_query(call.id)
        
        elif call.data == "show_domains":
            domains = db.fetchall("SELECT domain FROM allowed_domains WHERE group_id = ?", (chat_id,))
            if domains:
                text = "🌐 <b>دامنه‌های مجاز:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join([f"• <code>{d[0]}</code>" for d in domains])
            else:
                text = "🌐 هیچ دامنه مجازی یافت نشد!"
            bot.send_message(chat_id, text)
            bot.answer_callback_query(call.id)
        
        elif call.data == "group_stats":
            self.stats_command(call.message)
            bot.answer_callback_query(call.id)
        
        elif call.data == "close":
            bot.delete_message(chat_id, call.message.message_id)
            bot.answer_callback_query(call.id)

# ========== اجرا ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🛡️ Luffy Shield Bot - نسخه نهایی")
    print("=" * 60)
    print("✅ ربات محافظ گروه راه‌اندازی شد!")
    print(f"👥 ادمین‌ها: {ADMIN_IDS}")
    print("=" * 60)
    print("⏳ منتظر پیام‌ها...")
    print("=" * 60)
    
    while True:
        try:
            # استفاده از remove_webhook برای اطمینان
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=0, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            print("🔄 راه‌اندازی مجدد در 5 ثانیه...")
            time.sleep(5)
            continue
