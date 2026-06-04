import asyncio
from telegram import User
from handlers.admin_modules.menu import handle_menu_navigation

class MockQuery:
    def __init__(self):
        self.data = "menu_db_sync"
        self.from_user = User(id=1072002664, first_name="Test", is_bot=False) # Owner ID from .env
        
    async def answer(self):
        pass

    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        print('Message updated via handle_menu_navigation!')

class MockUpdate:
    def __init__(self):
        self.callback_query = MockQuery()
        self.effective_user = self.callback_query.from_user

async def main():
    try:
        await handle_menu_navigation(MockUpdate(), None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
