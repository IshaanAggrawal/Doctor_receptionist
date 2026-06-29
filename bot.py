import os
import logging
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import datetime

# Import our backend services
from src.services.slot_service import fetch_slots
from src.services.otp_service import generate_and_send_otp, verify_otp
from src.services.booking_service import book_slot
from src.utils.validators import validate_phone
from src.services.queue_service import get_live_queue

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Hardcoded for boilerplate (would be dynamic or tied to the bot instance in production)
CLINIC_ID = "00000000-0000-0000-0000-000000000000"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point when user types /start"""
    await update.message.reply_text(
        "👋 Welcome to the DentaQ Booking Bot!\n\n"
        "To book an appointment, please reply with your mobile number (e.g. 03001234567)."
    )
    # Set state in context
    context.user_data['state'] = 'ASK_PHONE'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text messages based on the current state."""
    state = context.user_data.get('state')
    text = update.message.text.strip()
    
    if state == 'ASK_PHONE':
        clean_phone = validate_phone(text)
        if not clean_phone:
            await update.message.reply_text("❌ Invalid format. Please enter a valid phone number (e.g., 03001234567).")
            return
            
        # Send OTP
        success = generate_and_send_otp(clean_phone)
        if success:
            context.user_data['phone'] = clean_phone
            context.user_data['state'] = 'VERIFY_OTP'
            await update.message.reply_text(f"✅ An SMS with a 6-digit OTP has been sent to {clean_phone}.\n\nPlease reply with the 6-digit code.")
        else:
            await update.message.reply_text("❌ Failed to send OTP. Please try again later.")
            
    elif state == 'VERIFY_OTP':
        phone = context.user_data.get('phone')
        otp_result = verify_otp(phone, text)
        
        if not otp_result["success"]:
            await update.message.reply_text(f"❌ {otp_result['message']}")
            return
            
        # OTP is correct! Now show slots.
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        slots = fetch_slots(CLINIC_ID, today)
        
        if not slots:
            await update.message.reply_text("I'm sorry, but there are no slots available today.")
            context.user_data.clear()
            return
            
        keyboard = []
        # Create a grid of 2 buttons per row
        row = []
        for slot in slots:
            raw_time = slot['slot_time'].split("T")[1][:5]
            dt_obj = datetime.datetime.strptime(raw_time, "%H:%M")
            formatted_time = dt_obj.strftime("%I:%M %p")
            
            # The callback_data will be the slot ID
            row.append(InlineKeyboardButton(formatted_time, callback_data=slot['id']))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.user_data['state'] = 'SELECT_SLOT'
        
        await update.message.reply_text(
            "✅ Phone verified!\n\nPlease select an available slot below:",
            reply_markup=reply_markup
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button clicks (slot selection)."""
    query = update.callback_query
    await query.answer()
    
    if context.user_data.get('state') != 'SELECT_SLOT':
        await query.edit_message_text("❌ Session expired. Please type /start to begin again.")
        return
        
    slot_id = query.data
    phone = context.user_data.get('phone')
    
    # We don't ask for a name in the bot for simplicity, we use the Telegram first name
    name = update.effective_user.first_name
    
    # Execute the Atomic Booking Transaction
    booking = book_slot(
        clinic_id=CLINIC_ID,
        slot_id=slot_id,
        patient_name=name,
        phone_number=phone,
        ip_address="TELEGRAM_BOT"
    )
    
    if booking["success"]:
        await query.edit_message_text(
            f"🎉 **Booking Confirmed!**\n\n"
            f"Your Token: **{booking['booking_token']}**\n"
            f"Time: {booking['slot_time']}\n"
            f"Queue Position: #{booking['queue_position']}\n\n"
            f"You can type /mystatus at any time to see your current queue position."
        )
        context.user_data.clear()
    else:
        # e.g., RACE_CONDITION (Someone clicked it right before them)
        await query.edit_message_text(f"❌ {booking['message']}\n\nPlease type /start to try again.")
        context.user_data.clear()

async def mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows patient to check their current queue position."""
    # Note: In a real app, you'd verify their phone again or link their Telegram User ID.
    # For boilerplate, we'll just demonstrate the queue lookup conceptually.
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    queue = get_live_queue(CLINIC_ID, today)
    
    if not queue:
        await update.message.reply_text("There are no active patients in the queue right now.")
        return
        
    await update.message.reply_text(
        f"📊 **Live Queue Status**\n"
        f"Currently Serving: {queue[0]['patient_name']}\n"
        f"Total Patients Waiting: {len(queue)}"
    )

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing in environment variables.")
        exit(1)
        
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mystatus", mystatus))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("🤖 Telegram Bot is running...")
    app.run_polling()
