# FSMstates.py

from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    waiting_for_password = State()
    waiting_for_confirm_password = State()
    waiting_for_email = State()  # ← новое

class LoginStates(StatesGroup):
    waiting_for_password = State()

class PasswordResetStates(StatesGroup):
    waiting_for_email = State()      # ← новое
    waiting_for_code = State()       # ← новое
    waiting_for_new_password = State()
    waiting_for_confirm_new_password = State()

class AuthStates(StatesGroup):
    authorized = State()

class ClientChatStates(StatesGroup):
    waiting_for_provider_id = State()
    in_chat = State()

class ProviderChatStates(StatesGroup):
    in_chat = State()

class ServiceRecordStates(StatesGroup):
    waiting_for_client_id = State()
    waiting_for_service_name = State()
    waiting_for_cost = State()
    waiting_for_address = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_comments = State()

class CalendarStates(StatesGroup):
    waiting_for_year = State()
    waiting_for_month = State()
    waiting_for_day = State()