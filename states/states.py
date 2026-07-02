from aiogram.fsm.state import State, StatesGroup

class ProfileStates(StatesGroup):
    waiting_for_region = State()
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_subject = State()

class AdminStates(StatesGroup):
    waiting_for_admin_id_to_add = State()
    waiting_for_admin_id_to_remove = State()
    
    # Mandatory channel adding states
    waiting_for_channel_id = State()
    waiting_for_channel_link = State()
    waiting_for_channel_title = State()
    
    # Test channel adding states
    waiting_for_test_channel_id = State()
    waiting_for_test_channel_link = State()
    waiting_for_test_channel_title = State()
    
    # Genre adding state
    waiting_for_genre_name = State()
    
    waiting_for_broadcast_msg = State()
    waiting_for_footer_text = State()

class TestCreationStates(StatesGroup):
    waiting_for_test_name = State()
    waiting_for_genre = State()
    waiting_for_file = State()
    waiting_for_keys = State()
    waiting_for_solutions = State()
    waiting_for_channel = State()
    waiting_for_start_time = State()
    waiting_for_duration = State()

class TestTakingStates(StatesGroup):
    waiting_for_answers = State()
