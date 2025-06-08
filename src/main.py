from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
import asyncio
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiohttp

bot = Bot(
    token="7406482300:AAHKtgL8of2e8yIAryRxt-K-LS0Zdk_n0xM",
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

FOOTBALL_API_TOKEN = '0386d167ecbe4253aed0854a77463271'

LEAGUES = {
    "Испанская Ла Лига": 2014,   # La Liga
    "Английская Премьер Лига": 2021,  # Premier League
    "Итальянская Серия А": 2019,  # Serie A
    "Немецкая Бундеслига": 2002,  # Bundesliga
    "Французская Лига 1": 2015  # Ligue 1
}

class FootballStates(StatesGroup):
    choosing_league = State()
    choosing_club = State()

# Кол-во игроков на странице
PLAYERS_PER_PAGE = 10

# CallbackData класс для страниц
class SquadPageCallback(CallbackData, prefix="squad"):
    page: int

def main_menu():
    items = list(LEAGUES.keys())
    builder = ReplyKeyboardBuilder()
    [builder.button(text=item) for item in items]
    builder.adjust(3,2,1)

    return builder.as_markup(resize_keyboard=True)

back_button = KeyboardButton(text="Назад")

def clubs_menu(clubs: list):
    items = clubs
    builder = ReplyKeyboardBuilder()
    [builder.button(text=item) for item in items]
    builder.button(text="Назад")
    builder.adjust(5,5,5,5,1)

    return builder.as_markup(resize_keyboard=True)

def get_squad_keyboard(page: int, max_page: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=SquadPageCallback(page=page - 1).pack()))
    if page < max_page - 1:
        buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=SquadPageCallback(page=page + 1).pack()))
    if buttons:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons],row_width=2)
    return keyboard

async def format_squad_page(squad: list, page: int) -> str:
    start = page * PLAYERS_PER_PAGE
    end = start + PLAYERS_PER_PAGE
    players = squad[start:end]
    lines = []
    for p in players:
        name = p.get('name', '—')
        position = p.get('position', '—')
        number = p.get('shirtNumber', '—')
        lines.append(f"{name} - {position} - {number}")
    return "\n".join(lines) if lines else "Список игроков отсутствует."

async def fetch_json(url):
    headers = {"X-Auth-Token": FOOTBALL_API_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                return None

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()  # очистить состояние
    await message.answer(
        f'Привет, {message.from_user.first_name}! Я - футбольный бот-статистик.\n\n'
        'Я предоставляю информацию о:\n'
        '- Футбольных лигах\n'
        '- Клубах\n'
        '- Игроках\n\n'
        'Используй клавиатуру для навигации!',
        reply_markup=main_menu()
    )
    await state.set_state(FootballStates.choosing_league)

@dp.message(F.text.in_(list(LEAGUES.keys())), FootballStates.choosing_league)
async def league_info(message: Message, state: FSMContext):
    league_name = message.text
    league_id = LEAGUES[league_name]

    await state.update_data(selected_league_id=league_id)

    url = f"https://api.football-data.org/v4/competitions/{league_id}"
    data = await fetch_json(url)
    if not data:
        await message.answer("Не удалось получить информацию по лиге.")
        return

    current_season = data.get('currentSeason', {})
    winner = current_season.get('winner')

    if winner:
        winner_text = f"Победитель прошлого сезона: {winner.get('name', '—')}"
    else:
        winner_text = "Чемпионат ещё не закончен"

    text = (
        f"🏆 <b>{data.get('name', '—')}</b>\n"
        f"Страна: {data.get('area', {}).get('name', '—')}\n"
        f"Сезон: {current_season.get('startDate', '—')} - {current_season.get('endDate', '—')}\n"
        f"Текущий тур: {current_season.get('currentMatchday', '—')}\n"
    )

    emblem_url = data.get('emblem')

    teams_url = f"https://api.football-data.org/v4/competitions/{league_id}/teams"
    teams_data = await fetch_json(teams_url)
    if not teams_data:
        await message.answer("Не удалось получить список команд.")
        return

    team_names = [team['name'] for team in teams_data.get('teams', [])]

    if emblem_url:
        await message.answer_photo(
            photo=emblem_url,
            caption=text,
            parse_mode='HTML',
            reply_markup=clubs_menu(team_names)
        )
    else:
        await message.answer(
            text,
            parse_mode='HTML',
            reply_markup=clubs_menu(team_names)
        )

    await state.set_state(FootballStates.choosing_club)



@dp.message(F.text.lower() == "назад", FootballStates.choosing_club)
async def back_to_leagues(message: Message, state: FSMContext):
    await message.answer("Выбери футбольную лигу:", reply_markup=main_menu())
    await state.set_state(FootballStates.choosing_league)

@dp.message(F.text, FootballStates.choosing_club)
async def club_info(message: Message, state: FSMContext):
    data = await state.get_data()
    league_id = data.get('selected_league_id')

    if not league_id:
        await message.answer("Пожалуйста, сначала выберите лигу.", reply_markup=main_menu())
        await state.set_state(FootballStates.choosing_league)
        return

    club_name = message.text
    teams_url = f"https://api.football-data.org/v4/competitions/{league_id}/teams"
    teams_data = await fetch_json(teams_url)
    if not teams_data:
        await message.answer("Не удалось получить список команд.")
        return

    found_club = None
    for team in teams_data.get('teams', []):
        if team['name'].lower() == club_name.lower():
            found_club = team
            break

    if not found_club:
        await message.answer("Не удалось найти такой клуб. Попробуйте выбрать из списка.")
        return

    club_crest = found_club.get('crest')

    # 1. Отправляем основную информацию и эмблему (если есть)
    club_text = (
        f"⚽ <b>{found_club['name']}</b>\n"
        f"Краткое имя: <b>{found_club.get('shortName', '—')}</b>\n"
        f"Основан: <b>{found_club.get('founded', '—')}</b>\n"
        f"Стадион: <b>{found_club.get('venue', '—')}</b>\n"
        f"Адрес: <b>{found_club.get('address', '—')}</b>\n"
        f"Веб-сайт: <b>{found_club.get('website', '—')}</b>\n"
    )

    if club_crest:
        await message.answer_photo(photo=club_crest, caption=club_text, parse_mode='HTML')
    else:
        await message.answer(club_text, parse_mode='HTML')

    # 2. Получаем состав команды
    squad_url = f"https://api.football-data.org/v4/teams/{found_club['id']}"
    squad_data = await fetch_json(squad_url)
    squad = squad_data.get('squad', []) if squad_data else []

    # Сохраняем состав в состояние и отправляем первую страницу состава
    await state.update_data(squad=squad, club_name=found_club['name'])

    await send_squad_page(message.chat.id, squad, 0, found_club['name'])


async def send_squad_page(chat_id: int, squad: list, page: int, club_name: str, edit_message=None):
    PLAYERS_PER_PAGE = 10
    start = page * PLAYERS_PER_PAGE
    end = start + PLAYERS_PER_PAGE
    players = squad[start:end]

    lines = []
    for p in players:
        name = p.get('name', '—')
        position = p.get('position', '—')
        number = p.get('shirtNumber')
        if number is None:
            number_str = ""
        else:
            number_str = str(number)
        line = f"{name} - {position}" + (f" - {number_str}" if number_str else "")
        lines.append(line)

    text = f"<b>Состав команды {club_name} (страница {page + 1}):</b>\n" + "\n".join(lines)

    max_page = (len(squad) + PLAYERS_PER_PAGE - 1) // PLAYERS_PER_PAGE

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"squad_{page - 1}"))
    if page < max_page - 1:
        buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"squad_{page + 1}"))
    if buttons:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons], row_width=2)

    if edit_message:
        # Если редактируем уже отправленное сообщение
        await edit_message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)
    else:
        # Отправляем новое сообщение
        await bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=keyboard)


@dp.callback_query(lambda c: c.data and c.data.startswith("squad_"))
async def squad_page_callback_handler(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    data = await state.get_data()
    squad = data.get('squad', [])
    club_name = data.get('club_name', 'Команда')

    max_page = (len(squad) + 10 - 1) // 10
    if page < 0 or page >= max_page:
        await callback.answer("Нет такой страницы", show_alert=True)
        return

    await send_squad_page(callback.message.chat.id, squad, page, club_name, edit_message=callback.message)
    await callback.answer()


async def start_bot():
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("end")