import asyncio
from telegram import Update
from handlers.admin_modules.menu_db import show_db_sync_menu

class MockQuery:
    async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
        print('Message updated!')

async def main():
    await show_db_sync_menu(MockQuery())

if __name__ == "__main__":
    asyncio.run(main())
