import os
import json
import time
import asyncio
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8916888298:AAEIuLU0f4n_DuVXNhKj5bs22D5LtS0eWHA")
ADMIN_IDS = [7750636787]
CHANNEL_USERNAME = "@earnBd134"
CHANNEL_ID = "@earnBd134"
MIN_WITHDRAW = 100.0
TASK_REWARD = 5.0
REFERRAL_BONUS = 50.0
WAIT_SECONDS = 30

db = Database()

def is_admin(uid):
    return uid in ADMIN_IDS

async def check_joined(bot, uid):
    try:
        m = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=uid)
        return m.status not in ["left", "kicked"]
    except:
        return False

def main_kb(uid):
    btns = [
        [InlineKeyboardButton("📋 টাস্ক করুন", callback_data="tasks"), InlineKeyboardButton("💰 ব্যালেন্স", callback_data="balance")],
        [InlineKeyboardButton("💸 উইথড্র", callback_data="withdraw"), InlineKeyboardButton("👥 রেফার করুন", callback_data="refer")],
        [InlineKeyboardButton("🏆 লিডারবোর্ড", callback_data="leaderboard"), InlineKeyboardButton("ℹ️ সাহায্য", callback_data="help")]
    ]
    if is_admin(uid):
        btns.append([InlineKeyboardButton("⚙️ অ্যাডমিন প্যানেল", callback_data="admin")])
    return InlineKeyboardMarkup(btns)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    ref_id = int(args[0]) if args and args[0].isdigit() else None
    is_new = db.register_user(user.id, user.full_name, user.username, ref_id)
    if is_new and ref_id and ref_id != user.id:
        db.add_balance(ref_id, REFERRAL_BONUS)
        try:
            await context.bot.send_message(
                chat_id=ref_id,
                text=f"🎉 *{user.full_name}* আপনার রেফার লিংক দিয়ে যোগ দিয়েছে!\n✅ পেয়েছেন: *৳{REFERRAL_BONUS:.0f}*",
                parse_mode="Markdown"
            )
        except:
            pass
    joined = await check_joined(context.bot, user.id)
    if not joined:
        await update.message.reply_text(
            f"👋 *স্বাগতম {user.first_name}!*\n\n🤖 টাস্ক করে আয় করুন!\n\n⚠️ *প্রথমে চ্যানেল জয়েন করুন:*\n{CHANNEL_USERNAME}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 চ্যানেল জয়েন করুন", url="https://t.me/earnBd134")],
                [InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_join")]
            ])
        )
        return
    await show_menu(update, context, user)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user=None):
    if not user:
        user = update.effective_user
    bal = db.get_balance(user.id)
    text = f"🏠 *মেইন মেনু*\n\n👤 {user.full_name}\n💰 ব্যালেন্স: *৳{bal:.2f}*\n\n👇 অপশন বেছে নিন:"
    if hasattr(update, 'message') and update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_kb(user.id))
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_kb(user.id))

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await show_menu(update, context, q.from_user)

async def check_join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await check_joined(context.bot, q.from_user.id):
        await q.answer("❌ এখনো জয়েন করেননি!", show_alert=True)
        return
    await show_menu(update, context, q.from_user)

async def tasks_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    if not await check_joined(context.bot, user.id):
        await q.answer("❌ প্রথমে চ্যানেল জয়েন করুন!", show_alert=True)
        return
    tasks = db.get_active_tasks()
    if not tasks:
        await q.edit_message_text(
            "📋 *টাস্ক লিস্ট*\n\n😔 এখন কোনো টাস্ক নেই।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]])
        )
        return
    btns = []
    for t in tasks:
        done = db.is_task_completed(user.id, t["id"])
        btns.append([InlineKeyboardButton(f"{'✅' if done else '🔗'} {t['title']} | ৳{t['reward']:.0f}", callback_data=f"dotask_{t['id']}")])
    btns.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")])
    await q.edit_message_text(
        f"📋 *টাস্ক লিস্ট*\n\n✅ সম্পন্ন: {db.get_completed_count(user.id)} টি\n\n👇 টাস্কে ক্লিক করুন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(btns)
    )

async def dotask_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    task_id = int(q.data.split("_")[1])
    task = db.get_task(task_id)
    if not task:
        await q.answer("❌ টাস্ক নেই!", show_alert=True)
        return
    if db.is_task_completed(user.id, task_id):
        await q.answer("✅ আগেই সম্পন্ন!", show_alert=True)
        return
    context.user_data[f"t{task_id}_start"] = time.time()
    context.user_data[f"t{task_id}_ok"] = True
    await q.edit_message_text(
        f"📋 *{task['title']}*\n\n📝 {task['description']}\n\n💰 রিওয়ার্ড: *৳{task['reward']:.0f}*\n\n⚠️ *সঠিকভাবে করুন:*\n১. লিংকে ক্লিক করুন\n২. বিজ্ঞাপন দেখুন ও Skip চাপুন\n৩. ফিরে এসে ✅ চাপুন",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 টাস্ক লিংকে যান", url=task["link"])],
            [InlineKeyboardButton("✅ সম্পন্ন করেছি", callback_data=f"verify_{task_id}")],
            [InlineKeyboardButton("🔙 ফিরে যান", callback_data="tasks")]
        ])
    )

async def verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    task_id = int(q.data.split("_")[1])
    db.register_user(user.id, user.full_name, user.username, None)
    
    if db.is_task_completed(user.id, task_id):
        await q.answer("✅ ইতোমধ্যে সম্পন্ন!", show_alert=True)
        return
        
    task = db.get_task(task_id)
    if not task:
        return
    clicked = context.user_data.get(f"t{task_id}_ok", False)
    start_time = context.user_data.get(f"t{task_id}_start", None)
    if not clicked or not start_time:
        await q.edit_message_text(
            "❌ *যাচাই ব্যর্থ!*\n\nআপনি টাস্ক লিংকে যাননি!\nপ্রথমে *🔗 লিংকে যান* চাপুন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 আবার চেষ্টা", callback_data=f"dotask_{task_id}")]])
        )
        return
    elapsed = time.time() - start_time
    if elapsed < WAIT_SECONDS:
        remaining = WAIT_SECONDS - int(elapsed)
        await q.edit_message_text(
            f"⏳ *একতু অপেক্ষা করুন!*\n\nআরো *{remaining} সেকেন্ড* পরে verify করুন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 আবার লিংকে যান", url=task["link"])],
                [InlineKeyboardButton("✅ সম্পন্ন করেছি", callback_data=f"verify_{task_id}")]
            ])
        )
        return
        
    db.complete_task(user.id, task_id)
    db.add_balance(user.id, task["reward"])
    new_bal = db.get_balance(user.id)
    context.user_data.pop(f"t{task_id}_start", None)
    context.user_data.pop(f"t{task_id}_ok", None)
    await q.edit_message_text(
        f"🎉 *টাস্ক সম্পন্ন!*\n\n✅ যাচাই: সফল\n💰 পেয়েছেন: *৳{task['reward']:.0f}*\n💼 ব্যালেন্স: *৳{new_bal:.2f}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 আরো টাস্ক", callback_data="tasks")],
            [InlineKeyboardButton("🏠 মেইন মেনু", callback_data="menu")]
        ])
    )

async def balance_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    bal = db.get_balance(user.id)
    stats = db.get_user_stats(user.id)
    await q.edit_message_text(
        f"💰 *আপনার ব্যালেন্স*\n\n💵 বর্তমান: *৳{bal:.2f}*\n✅ সম্পন্ন টাস্ক: {stats['tasks_done']} টি\n👥 রেফার: {stats['referrals']} জন\n💸 মোট উইথড্র: ৳{stats['total_withdrawn']:.2f}\n\n💡 ন্যূনতম উইথড্র: *৳{MIN_WITHDRAW:.0f}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💸 উইথড্র করুন", callback_data="withdraw")], [InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]])
    )

async def withdraw_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bal = db.get_balance(q.from_user.id)
    if bal < MIN_WITHDRAW:
        await q.edit_message_text(
            f"💸 *উইথড্র*\n\n❌ ব্যালেন্স কম!\n\n💰 বর্তমান: ৳{bal:.2f}\n🎯 প্রয়োজন: ৳{MIN_WITHDRAW:.0f}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 টাস্ক করুন", callback_data="tasks")], [InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]])
        )
        return
    await q.edit_message_text(
        f"💸 *উইথড্র*\n\n💰 ব্যালেন্স: ৳{bal:.2f}\n\nপেমেন্ট মেথড বেছে নিন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 bKash", callback_data="wd_bkash"), InlineKeyboardButton("💜 Nagad", callback_data="wd_nagad")], [InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]])
    )

async def wd_method_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    method = q.data.split("_")[1].upper()
    context.user_data["wd_method"] = method
    context.user_data["awaiting_wd"] = True
    await q.edit_message_text(
        f"📱 *{method} উইথড্র*\n\nআপনার {method} নম্বর পাঠান:\n(01XXXXXXXXX)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ বাতিল", callback_data="menu")]])
    )

async def refer_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={user.id}"
    stats = db.get_user_stats(user.id)
    await q.edit_message_text(
        f"👥 *রেফারেল প্রোগ্রাম*\n\n🎁 প্রতি রেফারে: *৳{REFERRAL_BONUS:.0f}*\n👥 মোট রেফার: {stats['referrals']} জন\n\n🔗 *আপনার লিংক:*\n`{link}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 শেয়ার করুন", url=f"https://t.me/share/url?url={link}&text=টাস্ক+করে+আয়+করুন!")], [InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]])
    )

async def leaderboard_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    top = db.get_leaderboard()
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = "🏆 *টপ আর্নার*\n\n"
    for i, u in enumerate(top):
        earned_key = "total_earned" if "total_earned" in u else "balance"
        text += f"{medals[i] if i<len(medals) else str(i+1)} {u['name']} — *৳{u.get(earned_key, 0.0):.2f}*\n"
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]]))

async def help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        f"ℹ️ *সাহায্য*\n\n📋 *কিভাবে আয় করবেন:*\n১. টাস্ক লিস্টে যান\n২. টাস্কে ক্লিক করুন\n৩. লিংকে যান ও বিজ্ঞাপন দেখুন\n৪. ✅ বাটন চাপুন → ৳{TASK_REWARD:.0f} পাবেন\n\n💸 *উইথড্র:* ন্যূনতম ৳{MIN_WITHDRAW:.0f} | bKash/Nagad\n👥 *রেফার:* প্রতিজনে ৳{REFERRAL_BONUS:.0f}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]])
    )

async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    s = db.get_bot_stats()
    await q.edit_message_text(
        f"⚙️ *অ্যাডমিন প্যানেল*\n\n👥 মোট ইউজার: {s['total_users']}\n✅ সম্পন্ন টাস্ক: {s['tasks_completed']}\n💸 মোট উইথড্র: ৳{s['total_withdrawn']:.2f}\n⏳ পেন্ডিং: {s['pending_withdrawals']} টি\n📋 সক্রিয় টাস্ক: {s['active_tasks']} টি",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ টাস্ক যোগ", callback_data="admin_addtask"), InlineKeyboardButton("🗑 টাস্ক মুছুন", callback_data="admin_deltask")],
            [InlineKeyboardButton("💸 পেন্ডিং উইথড্র", callback_data="admin_pending"), InlineKeyboardButton("📢 ব্রডকাস্ট", callback_data="admin_broadcast")],
            [InlineKeyboardButton("👥 ইউজার লিস্ট", callback_data="admin_users"), InlineKeyboardButton("🔙 ফিরে যান", callback_data="menu")]
        ])
    )

async def admin_addtask_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    context.user_data["adding_task"] = True
    context.user_data["task_step"] = 1
    await q.edit_message_text("➕ *নতুন টাস্ক*\n\nটাস্কের *শিরোনাম* দিন:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ বাতিল", callback_data="admin")]]))

async def admin_deltask_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    tasks = db.get_active_tasks()
    if not tasks:
        await q.answer("কোনো টাস্ক নেই!", show_alert=True)
        return
    btns = [[InlineKeyboardButton(f"🗑 {t['title']}", callback_data=f"deltask_{t['id']}")] for t in tasks]
    btns.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="admin")])
    await q.edit_message_text("🗑 *কোন টাস্কটি মুছবেন?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def deltask_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    db.delete_task(int(q.data.split("_")[1]))
    await q.answer("✅ মুছে ফেলা হয়েছে!", show_alert=True)
    await admin_cb(update, context)

async def admin_pending_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    reqs = db.get_pending_withdrawals()
    if not reqs:
        await q.edit_message_text("💸 কোনো পেন্ডিং নেই!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="admin")]]))
        return
    text = "💸 *পেন্ডিং উইথড্র:*\n\n"
    btns = []
    for r in reqs[:10]:
        text += f"🆔 #{r['id']} | {r['name']} | ৳{r['amount']:.0f} | {r['method']}: {r['phone']}\n"
        btns.append([InlineKeyboardButton(f"✅ #{r['id']} অ্যাপ্রুভ", callback_data=f"approve_{r['id']}"), InlineKeyboardButton(f"❌ রিজেক্ট", callback_data=f"reject_{r['id']}")]])
    btns.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="admin")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def approve_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    req_id = int(q.data.split("_")[1])
    req = db.get_withdrawal(req_id)
    if not req:
        return
    db.update_withdrawal(req_id, "approved")
    try:
        await context.bot.send_message(chat_id=req["user_id"], text=f"✅ *উইথড্র অ্যাপ্রুভ!*\n\n💰 ৳{req['amount']:.2f} → {req['method']}: {req['phone']}\n\nধন্যবাদ! 🎉", parse_mode="Markdown")
    except:
        pass
    await q.answer(f"✅ #{req_id} অ্যাপ্রুভ!", show_alert=True)

async def reject_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    req_id = int(q.data.split("_")[1])
    req = db.get_withdrawal(req_id)
    if not req:
        return
    db.update_withdrawal(req_id, "rejected")
    db.add_balance(req["user_id"], req["amount"])
    try:
        await context.bot.send_message(chat_id=req["user_id"], text=f"❌ *উইথড্র রিজেক্ট*\n\n৳{req['amount']:.2f} ব্যালেন্সে ফেরত দেওয়া হয়েছে।", parse_mode="Markdown")
    except:
        pass
    await q.answer(f"❌ #{req_id} রিজেক্ট!", show_alert=True)

async def admin_broadcast_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    context.user_data["broadcasting"] = True
    await q.edit_message_text("📢 *ব্রডকাস্ট*\n\nসবাইকে পাঠানোর মেসেজ লিখুন:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ বাতিল", callback_data="admin")]]))

async def admin_users_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    users = db.get_all_users()
    text = f"👥 *মোট ইউজার: {len(users)}*\n\n"
    for u in users[:20]:
        text += f"• {u['name']} — ৳{u['balance']:.2f}\n"
    if len(users) > 20:
        text += f"\n...আরো {len(users)-20} জন"
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="admin")]]))

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if context.user_data.get("broadcasting") and is_admin(user.id):
        msg = update.message.text
        users = db.get_all_users()
        sent = failed = 0
        for u in users:
            try:
                await context.bot.send_message(chat_id=u["user_id"], text=f"📢 *ঘোষণা:*\n\n{msg}", parse_mode="Markdown")
                sent += 1
                await asyncio.sleep(0.05)
            except:
                failed += 1
        context.user_data.clear()
        await update.message.reply_text(f"✅ পাঠানো: {sent}\n❌ ব্যর্থ: {failed}")
        return
        
    if context.user_data.get("awaiting_wd"):
        phone = update.message.text.strip()
        if not (phone.isdigit() and len(phone) == 11 and phone.startswith("01")):
            await update.message.reply_text("❌ সঠিক নম্বর দিন! (01XXXXXXXXX)")
            return
        method = context.user_data.get("wd_method", "bKash")
        bal = db.get_balance(user.id)
        if bal < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ ব্যালেন্স কম!")
            context.user_data.clear()
            return
        req_id = db.create_withdrawal(user.id, bal, method, phone)
        db.deduct_balance(user.id, bal)
        context.user_data.clear()
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=aid,
                    text=f"🔔 *নতুন উইথড্র!*\n\n🆔 #{req_id}\n👤 {user.full_name}\n💰 ৳{bal:.2f}\n📱 {method}: `{phone}`",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ অ্যাপ্রুভ", callback_data=f"approve_{req_id}"), InlineKeyboardButton("❌ রিজেক্ট", callback_data=f"reject_{req_id}")]])
                )
            except:
                pass
        await update.message.reply_text(f"✅ *উইথড্র রিকোয়েস্ট পাঠানো হয়েছে!*\n\n🆔 #{req_id}\n💰 ৳{bal:.2f}\n📱 {method}: {phone}\n\n⏳ ২৪ ঘণ্টার মধ্যে পেমেন্ট করা হবে।", parse_mode="Markdown", reply_markup=main_kb(user.id))
        return
        
    if is_admin(user.id) and context.user_data.get("adding_task"):
        step = context.user_data.get("task_step", 1)
        if step == 1:
            context.user_data["task_title"] = update.message.text.strip()
            context.user_data["task_step"] = 2
            await update.message.reply_text("📝 টাস্কের *বিবরণ* দিন:", parse_mode="Markdown")
        elif step == 2:
            context.user_data["task_desc"] = update.message.text.strip()
            context.user_data["task_step"] = 3
            await update.message.reply_text("🔗 *Droplink লিংক* পাঠান:", parse_mode="Markdown")
        elif step == 3:
            context.user_data["task_link"] = update.message.text.strip()
            context.user_data["task_step"] = 4
            await update.message.reply_text(f"💰 রিওয়ার্ড কত টাকা? (Default: {TASK_REWARD})", parse_mode="Markdown")
        elif step == 4:
            try:
                reward = float(update.message.text.strip())
            except:
                reward = TASK_REWARD
            tid = db.add_task(context.user_data["task_title"], context.user_data["task_desc"], context.user_data["task_link"], reward)
            title = context.user_data["task_title"]
            context.user_data.clear()
            await update.message.reply_text(f"✅ *টাস্ক যোগ হয়েছে!*\n\n🆔 #{tid}\n📋 {title}\n💰 ৳{reward:.0f}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ অ্যাডমিন", callback_data="admin")]]))

def setup_app(token):
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_join_cb, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(tasks_cb, pattern="^tasks$"))
    app.add_handler(CallbackQueryHandler(dotask_cb, pattern="^dotask_"))
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify_"))
    app.add_handler(CallbackQueryHandler(balance_cb, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(withdraw_cb, pattern="^withdraw$"))
    app.add_handler(CallbackQueryHandler(wd_method_cb, pattern="^wd_"))
    app.add_handler(CallbackQueryHandler(refer_cb, pattern="^refer$"))
    app.add_handler(CallbackQueryHandler(leaderboard_cb, pattern="^leaderboard$"))
    app.add_handler(CallbackQueryHandler(help_cb, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(admin_addtask_cb, pattern="^admin_addtask$"))
    app.add_handler(CallbackQueryHandler(admin_deltask_cb, pattern="^admin_deltask$"))
    app.add_handler(CallbackQueryHandler(deltask_cb, pattern="^deltask_"))
    app.add_handler(CallbackQueryHandler(admin_pending_cb, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(approve_cb, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(reject_cb, pattern="^reject$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast_cb, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_users_cb, pattern="^admin_users$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    return app

ptb_app = setup_app(BOT_TOKEN)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        async def process():
            update = Update.de_json(json.loads(post_data.decode('utf-8')), ptb_app.bot)
            await ptb_app.initialize()
            await ptb_app.process_update(update)
            await ptb_app.shutdown()
            
        asyncio.run(process())
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Earning Python Bot Engine is Live & Running!")
