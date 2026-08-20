"""Telegram Shop Manager: admin posting va PostgreSQL mahsulot qidiruvi."""
import asyncio
import io
import logging
import os
import tempfile
import uuid
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

import config
import state
from ai_helper import analyze_catalog_product, analyze_product_query, generate_caption_for_product, generate_post_from_image
from catalog import import_excel
from database import find_product_by_name, increase_product_quantity, init_db, list_products, search_products, upsert_products
from poster import pick_products_to_post
from retrieval import match_image, retrieve

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger("telegram_shop_bot")


def _is_admin(update: Update) -> bool:
    return bool(update.effective_chat and update.effective_chat.id in config.ADMIN_CHAT_IDS)


def _get_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Kanalga joylash", callback_data="publish_post"),
                                  InlineKeyboardButton("🔄 Qayta yozish", callback_data="regen_post")],
                                 [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_post")]])


def _get_auto_post_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Kanalga joylash", callback_data="auto_publish")],
                                 [InlineKeyboardButton("🔄 Qayta yozish", callback_data="auto_regen"),
                                  InlineKeyboardButton("➡️ Boshqa mahsulot", callback_data="auto_next")]])


def _get_quantity_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Ha, sonini oshirish", callback_data="add_qty_yes"),
                                  InlineKeyboardButton("❌ Yo'q", callback_data="add_qty_no")]])


def _get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["/add", "/import"], ["/post", "/avtopost"]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Admin buyrug'ini tanlang",
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _is_admin(update):
        text = (f"Salom, <b>{update.effective_user.first_name}</b>!\n\n"
                f"⚡️ <b>{config.SHOP_NAME}</b> admin rejimi.\n\n"
                "/add — rasm + nom bilan mahsulot qo'shish\n"
                "/post — rasm + caption bilan kanal posti\n"
                "/import — Excel fayl yuborib import qilish\n"
                "/avtopost — DB'dan navbatdagi mahsulotni kanalga chiqarish")
    else:
        text = (f"Assalomu alaykum, <b>{update.effective_user.first_name}</b>!\n\n"
                f"🛍 <b>{config.SHOP_NAME}</b> do'koniga xush kelibsiz!\n\n"
                "Nima izlayapsiz? Mahsulot nomini yozing yoki rasmini yuboring.")
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=_get_admin_reply_keyboard() if _is_admin(update) else None,
    )


async def cmd_post_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return
    context.user_data.clear()
    context.user_data["admin_mode"] = "post"
    await update.message.reply_text("📣 Post rejimi yoqildi. Kanalga qo'ymoqchi bo'lgan mahsulot rasmini captionida nomi/izohi bilan yuboring.")


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return
    context.user_data.clear()
    context.user_data["admin_mode"] = "add"
    await update.message.reply_text("➕ Mahsulot qo'shish rejimi. Rasm yuboring va captionida mahsulot nomini yozing.")


async def cmd_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    context.user_data.clear()
    context.user_data["admin_mode"] = "import"
    await update.message.reply_text("📊 Excel rejimi yoqildi. `.xlsx` faylni yuboring.")


async def cmd_auto_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        await update.message.reply_text("Bu buyruq faqat admin uchun.")
        return
    products = list_products(only_in_stock=config.ONLY_IN_STOCK)
    if not products:
        await update.message.reply_text("Qoldiqdagi mahsulot topilmadi.")
        return
    chosen = pick_products_to_post(products, 1)
    if not chosen:
        await update.message.reply_text("Post uchun mahsulot topilmadi.")
        return
    product = chosen[0]
    # Mahsulot preview ko'rilgan zahoti state'ga tushadi va qayta tanlanmaydi.
    state.mark_posted(product.id)
    caption = await _generate_catalog_post_with_typing(context, update.effective_chat.id, product)
    context.user_data["pending_auto_post"] = {
        "product_id": product.id,
        "name": product.name,
        "image_path": product.image_path,
        "caption": caption,
    }
    await _send_auto_preview(update, product, caption)


async def _generate_catalog_post(product) -> str:
    if product.image_path and os.path.exists(product.image_path):
        with open(product.image_path, "rb") as image:
            return await generate_post_from_image(image.read(), "image/jpeg", "")
    text = await generate_caption_for_product(product.name, product.price, product.category, product.qty)
    return text or f"<b>{product.name}</b>\n📂 Kategoriya: {product.category or 'Elektronika'}"


async def _generate_catalog_post_with_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int, product) -> str:
    """Gemini javobini kutayotganda Telegram'da typing holatini ushlab turadi."""
    task = asyncio.create_task(_generate_catalog_post(product))
    try:
        while not task.done():
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4)
        return await task
    finally:
        if not task.done():
            task.cancel()


async def _send_auto_preview(update: Update, product, caption: str) -> None:
    if product.image_path and os.path.exists(product.image_path):
        with open(product.image_path, "rb") as image:
            await update.effective_message.reply_photo(photo=image, caption=caption, parse_mode=ParseMode.HTML,
                                                       reply_markup=_get_auto_post_keyboard())
    else:
        await update.effective_message.reply_text(caption, parse_mode=ParseMode.HTML,
                                                   reply_markup=_get_auto_post_keyboard())


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.photo:
        return
    if not _is_admin(update):
        await _search_by_photo(update)
        return
    mode = context.user_data.get("admin_mode")
    if mode not in {"add", "post"}:
        await message.reply_text("Avval command yuboring: /add, /post yoki /import.")
        return
    if mode == "post":
        if message.media_group_id:
            album = context.user_data.setdefault("post_album", {"file_ids": [], "caption": "", "message": message})
            if message.photo[-1].file_id not in album["file_ids"]:
                album["file_ids"].append(message.photo[-1].file_id)
            if message.caption:
                album["caption"] = message.caption.strip()
            old_task = context.user_data.get("post_album_task")
            if old_task:
                old_task.cancel()
            context.user_data["post_album_task"] = asyncio.create_task(_process_post_album(context, update.effective_chat.id))
            return
        photo = message.photo[-1]
        user_caption = (message.caption or "").strip()
        if user_caption:
            # Admin tayyor caption bergan bo'lsa Gemini chaqirilmaydi va token sarflanmaydi.
            caption = user_caption
        else:
            status = await message.reply_text("⏳ Rasm tahlil qilinib, kanal posti tayyorlanmoqda...")
            caption = await generate_post_from_image_from_telegram(photo, "", context)
            await status.delete()
        context.user_data["pending_post"] = {"file_id": photo.file_id, "caption": caption, "user_note": user_caption}
        await message.reply_photo(photo=photo.file_id, caption=f"📝 <b>Post preview:</b>\n\n{caption}", parse_mode=ParseMode.HTML, reply_markup=_get_preview_keyboard())
        return
    if not message.caption or not message.caption.strip():
        context.user_data["pending_add_photo"] = message.photo[-1].file_id
        await message.reply_text("Mahsulot nomi majburiy. Rasm captioniga nomini yozing yoki keyingi xabarda faqat nomini yuboring.")
        return
    await _add_catalog_photo(update, context, message.photo[-1].file_id, message.caption.strip())


async def _process_post_album(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    await asyncio.sleep(1.2)
    album = context.user_data.pop("post_album", None)
    context.user_data.pop("post_album_task", None)
    if not album:
        return
    images = []
    for file_id in album["file_ids"]:
        photo_file = await context.bot.get_file(file_id)
        stream = io.BytesIO()
        await photo_file.download_to_memory(out=stream)
        images.append(stream.getvalue())
    note = album["caption"]
    if note:
        caption = note
    else:
        caption = await generate_post_from_image(images, "image/jpeg", "")
    context.user_data["pending_post"] = {"file_ids": album["file_ids"], "caption": caption, "user_note": note}
    # Preview'da matn faqat bitta alohida xabarda chiqadi; rasmlarda takrorlanmaydi.
    media = [InputMediaPhoto(media=file_id) for file_id in album["file_ids"]]
    await context.bot.send_media_group(chat_id=chat_id, media=media)
    await context.bot.send_message(chat_id=chat_id, text="📝 <b>Album post preview</b>\n\n" + caption,
                                   parse_mode=ParseMode.HTML, reply_markup=_get_preview_keyboard())


async def generate_post_from_image_from_telegram(photo, note: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    photo_file = await photo.get_file()
    stream = io.BytesIO()
    await photo_file.download_to_memory(out=stream)
    return await generate_post_from_image(stream.getvalue(), "image/jpeg", note)


async def _add_catalog_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str, product_name: str) -> None:
    message = update.effective_message
    status = await message.reply_text("⏳ Gemini mahsulot va kategoriyani aniqlamoqda...")
    photo_file = await context.bot.get_file(file_id)
    stream = io.BytesIO()
    await photo_file.download_to_memory(out=stream)
    product = await analyze_catalog_product(stream.getvalue(), "image/jpeg", product_name)
    product["name"] = product_name
    existing = find_product_by_name(product_name, product.get("category", ""))
    if existing:
        context.user_data["pending_add_confirm"] = {"product_id": existing.id, "name": existing.name, "qty": existing.qty}
        context.user_data.pop("pending_add_photo", None)
        await status.edit_text(
            f"⚠️ Bazada bu mahsulot bor:\n<b>{existing.name}</b>\nHozirgi soni: {int(existing.qty)} dona\n\n"
            "Shu mahsulot sonini 1 taga oshiraymi?",
            parse_mode=ParseMode.HTML,
            reply_markup=_get_quantity_keyboard(),
        )
        return
    os.makedirs(config.IMAGES_DIR, exist_ok=True)
    image_path = os.path.join(config.IMAGES_DIR, f"catalog_{uuid.uuid4().hex}.jpg")
    with open(image_path, "wb") as image_file:
        image_file.write(stream.getvalue())
    product["image_path"] = image_path
    upsert_products([product])
    context.user_data.pop("pending_add_photo", None)
    context.user_data.pop("admin_mode", None)
    await status.edit_text(f"✅ Mahsulot DB'ga qo'shildi.\nNomi: {product_name}\nKategoriya: {product['category']}\nQoldiq: {int(product['quantity'])} dona")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if context.user_data.get("admin_mode") not in {"add", "import"}:
        await update.effective_message.reply_text("Avval /add yoki /import commandini yuboring, keyin Excel faylni tashlang.")
        return
    document = update.effective_message.document
    if not document or not (document.file_name or "").lower().endswith((".xlsx", ".xls")):
        await update.effective_message.reply_text("Excel fayl (.xlsx yoki .xls) yuboring.")
        return
    status = await update.effective_message.reply_text("⏳ Excel tekshirilmoqda va PostgreSQL'ga import qilinmoqda...")
    file = await document.get_file()
    with tempfile.NamedTemporaryFile(suffix=os.path.splitext(document.file_name)[1], delete=False) as temp:
        path = temp.name
    try:
        await file.download_to_drive(path)
        count = import_excel(path)
        context.user_data.pop("admin_mode", None)
        await status.edit_text(f"✅ {count} ta mahsulot PostgreSQL'ga qo'shildi/yangilandi.")
    except Exception as exc:
        logger.exception("Admin Excel import xatosi")
        await status.edit_text(f"❌ Excel import xatosi: {exc}")
    finally:
        if os.path.exists(path):
            os.unlink(path)


async def _send_products(update: Update, products) -> None:
    for product in products:
        caption = (f"<b>{product.name}</b>\n📂 Kategoriya: {product.category or 'Boshqa'}\n"
                   f"✅ Mavjud: <b>{int(product.qty)} dona</b>").replace(",", " ")
        if product.image_path and os.path.exists(product.image_path):
            with open(product.image_path, "rb") as image:
                await update.effective_message.reply_photo(photo=image, caption=caption, parse_mode=ParseMode.HTML)
        else:
            await update.effective_message.reply_text(caption, parse_mode=ParseMode.HTML)


async def _send_search_results(update: Update, query: str, category: str = "") -> None:
    exact, similar = retrieve(query, category=category, limit=5)
    if not exact and not similar:
        await update.effective_message.reply_text("Afsuski, bunday mahsulot topilmadi. Boshqa nom yoki rasm yuboring.")
        return
    if exact:
        await update.effective_message.reply_text("🔎 <b>Topilgan mahsulotlar:</b>", parse_mode=ParseMode.HTML)
        await _send_products(update, exact)
    if similar:
        await update.effective_message.reply_text("📂 <b>Shu kategoriyadagi o'xshash mahsulotlar:</b>", parse_mode=ParseMode.HTML)
        await _send_products(update, similar)


async def _search_by_photo(update: Update) -> None:
    message = update.effective_message
    status = await message.reply_text("⏳ Rasm tahlil qilinib, katalogdan qidirilmoqda...")
    photo_file = await message.photo[-1].get_file()
    stream = io.BytesIO()
    await photo_file.download_to_memory(out=stream)
    image_bytes = stream.getvalue()
    # Gemini limit/timeout bo'lsa ham caption yoki katalogdagi ayni rasm ishlaydi.
    if message.caption:
        exact, similar = retrieve(message.caption)
        if exact or similar:
            await status.delete()
            await _send_search_results(update, message.caption)
            return
    image_matches = match_image(image_bytes)
    if image_matches:
        await status.delete()
        await _send_products(update, image_matches)
        return
    catalog = [item.name for item in list_products(only_in_stock=True)]
    result = await analyze_product_query(image_bytes, "image/jpeg", message.caption or "", catalog_names=catalog)
    await status.delete()
    matched_name = result.get("matched_name", "")
    if not matched_name or result.get("confidence", 0) < 0.65:
        await update.effective_message.reply_text("Bu rasm bo'yicha katalogda aniq mahsulot topilmadi. Mahsulot nomini yozib yuboring.")
        return
    await _send_search_results(update, matched_name, result.get("category", ""))


async def handle_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_message.text:
        return
    message = update.effective_message
    if _is_admin(update):
        if context.user_data.get("admin_mode") == "add" and context.user_data.get("pending_add_photo"):
            await _add_catalog_photo(update, context, context.user_data["pending_add_photo"], message.text.strip())
        else:
            await message.reply_text("Avval /add, /post yoki /import commandini tanlang.")
        return
    await message.reply_text("⏳ Katalogdan qidirilmoqda...")
    result = await analyze_product_query(user_text=message.text)
    await _send_search_results(update, result.get("keywords") or result.get("name") or message.text, result.get("category", ""))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _is_admin(update):
        await query.edit_message_caption(caption="Ruxsat berilmagan.")
        return
    if query.data == "add_qty_no":
        context.user_data.pop("pending_add_confirm", None)
        context.user_data.pop("admin_mode", None)
        await query.edit_message_text("❌ Yangi mahsulot qo'shilmadi.")
        return
    if query.data == "add_qty_yes":
        pending_add = context.user_data.pop("pending_add_confirm", None)
        if not pending_add:
            await query.edit_message_text("⚠️ Tasdiqlash ma'lumoti topilmadi. /add bilan qayta boshlang.")
            return
        product = increase_product_quantity(pending_add["product_id"])
        context.user_data.pop("admin_mode", None)
        await query.edit_message_text(f"✅ <b>{product.name}</b> soni oshirildi: {int(product.qty)} dona.", parse_mode=ParseMode.HTML)
        return
    if query.data in {"auto_publish", "auto_regen", "auto_next"}:
        pending_auto = context.user_data.get("pending_auto_post")
        if not pending_auto:
            await query.edit_message_text("⚠️ Tanlangan mahsulot topilmadi. /avtopost ni qayta bosing.")
            return
        products = list_products(only_in_stock=config.ONLY_IN_STOCK)
        product = next((item for item in products if item.id == pending_auto["product_id"]), None)
        if not product:
            await query.edit_message_text("⚠️ Mahsulot bazadan topilmadi.")
            context.user_data.pop("pending_auto_post", None)
            return
        if query.data == "auto_publish":
            try:
                if product.image_path and os.path.exists(product.image_path):
                    with open(product.image_path, "rb") as image:
                        await context.bot.send_photo(chat_id=config.CHANNEL_ID, photo=image,
                                                     caption=pending_auto["caption"], parse_mode=ParseMode.HTML)
                else:
                    await context.bot.send_message(chat_id=config.CHANNEL_ID, text=pending_auto["caption"],
                                                   parse_mode=ParseMode.HTML)
                if query.message.photo:
                    await query.edit_message_caption(caption="✅ Kanalga joylandi!\n\n" + pending_auto["caption"], parse_mode=ParseMode.HTML)
                else:
                    await query.edit_message_text("✅ Kanalga joylandi!")
            except Exception as exc:
                logger.exception("Avtopostni kanalga joylash xatosi")
                await query.edit_message_text(f"❌ Kanalga joylashda xatolik: {exc}")
            finally:
                context.user_data.pop("pending_auto_post", None)
            return
        if query.data == "auto_regen":
            if query.message.photo:
                await query.edit_message_caption(caption="⏳ Qayta yozilmoqda...")
            else:
                await query.edit_message_text("⏳ Qayta yozilmoqda...")
            caption = await _generate_catalog_post_with_typing(context, update.effective_chat.id, product)
            pending_auto["caption"] = caption
            if query.message.photo:
                await query.edit_message_caption(caption=caption, parse_mode=ParseMode.HTML, reply_markup=_get_auto_post_keyboard())
            else:
                await query.edit_message_text(caption, parse_mode=ParseMode.HTML, reply_markup=_get_auto_post_keyboard())
            return
        context.user_data.pop("pending_auto_post", None)
        next_products = list_products(only_in_stock=config.ONLY_IN_STOCK)
        chosen = pick_products_to_post(next_products, 1)
        if not chosen:
            await query.edit_message_text("✅ Barcha mahsulotlar ko'rib chiqildi. Keyingi aylanish boshlandi.")
            return
        next_product = chosen[0]
        state.mark_posted(next_product.id)
        caption = await _generate_catalog_post(next_product)
        context.user_data["pending_auto_post"] = {"product_id": next_product.id, "name": next_product.name,
                                                    "image_path": next_product.image_path, "caption": caption}
        await query.delete_message()
        await _send_auto_preview(update, next_product, caption)
        return
    pending = context.user_data.get("pending_post")
    if query.data == "cancel_post":
        context.user_data.pop("pending_post", None)
        context.user_data.pop("admin_mode", None)
        await _edit_post_message(query, "❌ Post bekor qilindi.")
        return
    if not pending:
        context.user_data.pop("admin_mode", None)
        await _edit_post_message(query, "⚠️ Post topilmadi. Qaytadan rasm yuboring.")
        return
    if query.data == "publish_post":
        try:
            if pending.get("file_ids"):
                media = [InputMediaPhoto(media=file_id, caption=pending["caption"] if index == 0 else None,
                                         parse_mode=ParseMode.HTML) for index, file_id in enumerate(pending["file_ids"])]
                await context.bot.send_media_group(chat_id=config.CHANNEL_ID, media=media)
            else:
                await context.bot.send_photo(chat_id=config.CHANNEL_ID, photo=pending["file_id"], caption=pending["caption"], parse_mode=ParseMode.HTML)
            await _edit_post_message(query, "✅ Kanalga joylandi!\n\n" + pending["caption"])
        except Exception as exc:
            logger.exception("Kanalga post joylash xatosi")
            await _edit_post_message(query, f"❌ Xatolik: {exc}")
        finally:
            context.user_data.pop("pending_post", None)
            context.user_data.pop("admin_mode", None)
    elif query.data == "regen_post":
        await _edit_post_message(query, "⏳ Qayta yozilmoqda...")
        file_ids = pending.get("file_ids") or [pending["file_id"]]
        images = []
        for file_id in file_ids:
            photo_file = await context.bot.get_file(file_id)
            stream = io.BytesIO()
            await photo_file.download_to_memory(out=stream)
            images.append(stream.getvalue())
        pending["caption"] = await generate_post_from_image(images, "image/jpeg", pending.get("user_note", ""))
        await _edit_post_message(query, "📝 <b>Yangi preview:</b>\n\n" + pending["caption"], reply_markup=_get_preview_keyboard())


async def _edit_post_message(query, text: str, reply_markup=None) -> None:
    if query.message and query.message.photo:
        await query.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    else:
        await query.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


def main() -> None:
    if not config.BOT_TOKEN or not config.CHANNEL_ID:
        raise SystemExit("BOT_TOKEN va CHANNEL_ID .env faylida bo'lishi shart.")
    if not config.ADMIN_CHAT_IDS:
        raise SystemExit("ADMIN_CHAT_IDS .env faylida bo'lishi shart.")
    init_db()
    application = Application.builder().token(config.BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("post", cmd_post_now))
    application.add_handler(CommandHandler("add", cmd_add))
    application.add_handler(CommandHandler("avtopost", cmd_auto_post))
    application.add_handler(CommandHandler("import", cmd_import))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL & ~filters.COMMAND, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_search))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
