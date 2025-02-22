import os
import sys
import asyncio
import logging
import sqlite3
from contextlib import closing
from aiogram import Bot, Dispatcher, Router, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("Error: BOT_TOKEN environment variable not set.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DB_PATH = "bot_db.sqlite3"

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL
                );
            """)

def add_item(name: str, price: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            conn.execute("INSERT INTO items (name, price) VALUES (?, ?)", (name, price))

def list_items():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return conn.execute("SELECT id, name, price FROM items").fetchall()

def delete_item(id: int):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        with conn:
            conn.execute("DELETE FROM items WHERE id = ?", (id,))



class FSMAdminAdd(StatesGroup):
    name = State()
    price = State()

class FSMAdminDel(StatesGroup):
    choose_item = State()

router = Router()

@router.message(Command("add_item"))
async def start_add_item(message: types.Message, state: FSMContext):
    await message.answer("Введите полное название товара:")
    await state.set_state(FSMAdminAdd.name)

@router.message(FSMAdminAdd.name)
async def load_item(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену товара(в сомах):")
    await state.set_state(FSMAdminAdd.price)

@router.message(FSMAdminAdd.price)
async def load_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите цену (в сомах).")
        return

    price = int(message.text)
    data = await state.get_data()
    name = data.get("name")

    add_item(name, price)
    await message.answer(f'Товар "{name}" (цена: {price}) успешно добавлен!')
    await state.clear()

@router.message(Command("list_items"))
async def show_items(message: types.Message):
    items = list_items()
    if not items:
        await message.answer("В базе данных нет товаров.")
        return

    response = "\n".join([f"{id}. {name} - {price} сом" for id, name, price in items])
    await message.answer(f"Список товаров:\n{response}")

@router.callback_query(lambda call: call.data.startswith("remove_item_"))
async def process_remove_item(callback_query: types.CallbackQuery):
    item_id = int(callback_query.data.split("_")[2])
    delete_item(item_id)
    await callback_query.message.answer(f"Товар с ID {item_id} удален.")
    await callback_query.answer()

@router.message(Command("remove_item"))
async def start_remove_item(message: types.Message, state: FSMContext):
    items = list_items()
    if not items:
        await message.answer("В базе данных нет товаров для удаления.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{id}. {name} ({price} сом)",
            callback_data=f"remove_item_{id}"
        )] for id, name, price in items
    ])

    await message.answer("Выберите товар для удаления:", reply_markup=kb)
    await state.set_state(FSMAdminDel.choose_item)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(f"""Добро пожаловать, {message.from_user.first_name}! Рад видеть вас.
Доступные команды:
/add_item — добавить новый товар
/list_items — показать все товары
/remove_item — удалить товар""")

def register_handlers():
    dp.include_router(router)

async def main():
    init_db()
    register_handlers()

    print("Бот запущен!")
    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        pass
    finally:
        print("Бот завершил работу!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

