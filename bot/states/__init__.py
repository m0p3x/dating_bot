from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    height = State()
    city = State()
    goal = State()
    interests = State()
    bio = State()
    photo = State()


class EditProfile(StatesGroup):
    choose_field = State()
    name = State()
    age = State()
    gender = State()
    height = State()
    city = State()
    goal = State()
    interests = State()
    bio = State()
    photo = State()


class SearchSetup(StatesGroup):
    gender = State()
    height = State()
    goal = State()
    interests = State()


class Browse(StatesGroup):
    viewing = State()
    viewing_likes = State()   # ← добавить
    writing_message = State()
    reporting = State()
    report_comment = State()


class AdminStates(StatesGroup):
    main = State()
    viewing_report = State()
    searching_user = State()
    broadcast_confirm = State()
    broadcast_text = State()
