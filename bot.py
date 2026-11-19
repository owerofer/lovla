import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORTALS_KEY = os.getenv("PORTALS_KEY")

if not BOT_TOKEN or not PORTALS_KEY:
    raise ValueError("BOT_TOKEN или PORTALS_KEY не установлены")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_max_price = {}

def get_main_keyboard(max_price=None):
    price_text = f"💰 Макс. цена: {max_price} TON" if max_price else "💰 Выбери максимальную цену"
    kb = [
        [InlineKeyboardButton(text=price_text, callback_data="choose_price")],
        [InlineKeyboardButton(text="🔍 Сканировать сейчас", callback_data="scan")],
        [
            InlineKeyboardButton(text="10", callback_data="price_10"),
            InlineKeyboardButton(text="20", callback_data="price_20"),
            InlineKeyboardButton(text="50", callback_data="price_50"),
        ],
        [
            InlineKeyboardButton(text="100", callback_data="price_100"),
            InlineKeyboardButton(text="200", callback_data="price_200"),
            InlineKeyboardButton(text="500", callback_data="price_500"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Бот для ловли дешёвых гифтов на Portals\n\n"
        "1. Выбери максимальную цену\n"
        "2. Нажми «Сканировать сейчас»",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data.startswith("price_"))
async def set_price(callback: types.CallbackQuery):
    price = int(callback.data.split("_")[1])
    user_max_price[callback.from_user.id] = price
    await callback.message.edit_text(
        f"✅ Максимальная цена: <b>{price} TON</b>\n\nТеперь жми «Сканировать сейчас»",
        reply_markup=get_main_keyboard(price),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "choose_price")
async def choose_price(callback: types.CallbackQuery):
    await callback.answer("Выбери цену кнопками ниже")

@dp.callback_query(F.data == "scan")
async def scan(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    max_price = user_max_price.get(user_id)

    if not max_price:
        await callback.answer("Сначала выбери максимальную цену!", show_alert=True)
        return

    await callback.message.edit_text(f"🔍 Сканирую Portals до <b>{max_price} TON</b>...", parse_mode="HTML")

    try:
        results = await search_portals(max_price)

        if not results:
            await callback.message.edit_text(
                f"Ничего не найдено до {max_price} TON.",
                reply_markup=get_main_keyboard(max_price)
            )
            return

        for item in results[:10]:
            text = (
                f"🎁 <b>{item['name']}</b>\n"
                f"🔢 Номер: <code>#{item['number']}</code>\n"
                f"💰 Цена: <b>{item['price']} TON</b>\n"
                f"🎨 Модель: {item['model']}\n"
                f"🖼 Фон: {item['backdrop']}\n"
            )
            if item.get("is_low_number"):
                text += "⭐ Низкий номер\n"
            if item.get("possible_mono"):
                text += "🖤 Возможно монохром\n"

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Открыть на Portals", url=item["url"])]
            ])
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

        await callback.message.answer(
            f"✅ Найдено: {len(results)} лотов",
            reply_markup=get_main_keyboard(max_price)
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка:\n<code>{str(e)[:300]}</code>",
            reply_markup=get_main_keyboard(max_price),
            parse_mode="HTML"
        )

async def search_portals(max_price: float):
    url = "https://portal-market.com/partners/nfts/search"
    headers = {"Authorization": f"partners {PORTALS_KEY}"}
    params = {
        "status": "listed",
        "max_price": str(max_price),
        "sort_by": "price asc",
        "limit": 30
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"API error {resp.status}: {text[:150]}")

            data = await resp.json()
            results = []

            for item in data.get("results", []):
                try:
                    price = float(item.get("price") or 0)
                    number = item.get("external_collection_number") or 0
                    model = item.get("model", {}).get("name") if isinstance(item.get("model"), dict) else str(item.get("model", "—"))
                    backdrop = item.get("backdrop", {}).get("name") if isinstance(item.get("backdrop"), dict) else str(item.get("backdrop", "—"))
                    name = item.get("name") or "Gift"
                    gift_id = item.get("id")
                    url_link = f"https://t.me/portals/market?startapp=gift_{gift_id}" if gift_id else "https://t.me/portals"

                    is_low = isinstance(number, int) and number <= 300
                    possible_mono = False
                    if model and backdrop:
                        ml, bl = model.lower(), backdrop.lower()
                        for color in ["black", "white", "red", "blue", "green", "purple", "pink", "gold", "silver"]:
                            if color in ml and color in bl:
                                possible_mono = True
                                break

                    results.append({
                        "name": name,
                        "number": number,
                        "price": price,
                        "model": model,
                        "backdrop": backdrop,
                        "url": url_link,
                        "is_low_number": is_low,
                        "possible_mono": possible_mono
                    })
                except:
                    continue

            return results

async def main():
    print("Бот запущен на Railway")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
