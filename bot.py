import os
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import pdfplumber
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import  BOT_TOKEN
from prompt import start_prompt, help_prompt, classifier_prompt, rfp_prompt, fallback_prompt
from flash_model import analyze_rfp

os.makedirs("downloads/rfps", exist_ok=True)

async def start_command(update, context):
    await update.message.reply_text("Processing your request. Please wait...")
    anaysis_result = await analyze_rfp(start_prompt)
    for chunk in split_message(anaysis_result):
        await update.message.reply_text(chunk)

async def help_command(update, context):
    await update.message.reply_text("Processing your request. Please wait...")
    anaysis_result = await analyze_rfp(help_prompt)
    for chunk in split_message(anaysis_result):
        await update.message.reply_text(chunk)

async def message_identifier(update, context):
    await update.message.reply_text("Processing your RFP. Please wait...")
    text = update.message.text
    doc = update.message.document
    caption = update.message.caption
    if doc and doc.mime_type == "application/pdf":
        file = await doc.get_file()
        file_path = f"downloads/rfps/{doc.file_name}"
        await file.download_to_drive(file_path)
        extracted_text = await text_extract(file_path)
        extracted_text = f"Caption: {caption}\n\n PDF Text:\n{extracted_text}"
        category = classifier_prompt.format(rfp_content=extracted_text)

        if category=="RFP":
            await update.message.reply_text("Analyzing RFP...")
            anaysis_result = await analyze_rfp(rfp_prompt.format(rfp_content=extracted_text))
            for chunk in split_message(anaysis_result):
                await update.message.reply_text(chunk)
        elif category=="COMPANY_QUERY":
            await update.message.reply_text("Analyzing company query...")
            anaysis_result = await analyze_rfp(fallback_prompt.format(user_message=extracted_text))
            for chunk in split_message(anaysis_result):
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text("Analyzing message content...")
            anaysis_result = await analyze_rfp(fallback_prompt.format(user_message=extracted_text))
            for chunk in split_message(anaysis_result):
                await update.message.reply_text(chunk)
    elif text:
        category = classifier_prompt.format(rfp_content=text)
        if category=="RFP":
            await update.message.reply_text("Analyzing RFP...")
            anaysis_result = await analyze_rfp(rfp_prompt.format(rfp_content=text))
            for chunk in split_message(anaysis_result):
                await update.message.reply_text(chunk)
        elif category=="COMPANY_QUERY":
            await update.message.reply_text("Analyzing company query...")
            anaysis_result = await analyze_rfp(fallback_prompt.format(user_message=text))
            for chunk in split_message(anaysis_result):
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text("Analyzing message content...")
            anaysis_result = await analyze_rfp(fallback_prompt.format(user_message=text))
            for chunk in split_message(anaysis_result):
                await update.message.reply_text(chunk)
    else:
        await update.message.reply_text("Please send a PDF file.")
        


# Text extraction function 
async def text_extract(pdf_path):
    extracted_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                extracted_text += text
    return extracted_text

# Function to split long messages into chunks
def split_message(message, chunk_size=4096):
    return [message[i:i+chunk_size] for i in range(0, len(message), chunk_size)]

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(
    MessageHandler(
        filters.TEXT | filters.Document.PDF,
        message_identifier
    )
)
app .run_polling()