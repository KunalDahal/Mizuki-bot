import json
import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from util import SYMBOL_FILE
from mizuki_editor.commands.admin import admin_only

def load_preserve_symbols():
    """Load symbols to preserve during emoji removal"""
    try:
        if not os.path.exists(SYMBOL_FILE):
            return []
        with open(SYMBOL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_preserve_symbols(symbols):
    """Save symbols to preserve during emoji removal"""
    try:
        with open(SYMBOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(symbols, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

@admin_only
async def add_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add new symbol to preserve (/as command)"""
    if not context.args:
        await update.message.reply_text("Usage: /as <symbol>")
        return
        
    symbol = context.args[0]
    symbols = load_preserve_symbols()
    
    if symbol in symbols:
        await update.message.reply_text("Symbol already exists in preserve list.")
        return
        
    symbols.append(symbol)
    if save_preserve_symbols(symbols):
        await update.message.reply_text(f"✅ Added symbol to preserve: {symbol}")
    else:
        await update.message.reply_text("❌ Failed to save symbol")

@admin_only
async def remove_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove symbol from preserve list (/rs command)"""
    if not context.args:
        await update.message.reply_text("Usage: /rs <symbol>")
        return
        
    symbol = context.args[0]
    symbols = load_preserve_symbols()
    
    if symbol not in symbols:
        await update.message.reply_text("Symbol not found in preserve list.")
        return
        
    symbols.remove(symbol)
    if save_preserve_symbols(symbols):
        await update.message.reply_text(f"✅ Removed symbol: {symbol}")
    else:
        await update.message.reply_text("❌ Failed to remove symbol")

def get_handlers():
    return [
        CommandHandler("as", add_symbol),
        CommandHandler("rs", remove_symbol)
    ]