from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from handlers.user_modules import USER_DURATION, USER_PAYMENT_UPLOAD
from handlers.user_modules.start import start_command
from handlers.user_modules.plans import plan_command, show_plans_list, handle_plan_selection, handle_duration_selection
from handlers.user_modules.payment import receive_payment_screenshot, handle_payment_upload_back, cancel_user_flow

def get_user_handlers() -> list:
    plan_conv = ConversationHandler(
        entry_points=[
            CommandHandler("plan", plan_command),
            CallbackQueryHandler(show_plans_list, pattern="^select_plans_menu$"),
            CallbackQueryHandler(handle_plan_selection, pattern="^select_plan_")
        ],
        states={
            USER_DURATION: [
                CommandHandler("plan", plan_command),
                CallbackQueryHandler(show_plans_list, pattern="^select_plans_menu$"),
                CallbackQueryHandler(handle_duration_selection, pattern="^(sel_dur_|back_to_plans)"),
                CallbackQueryHandler(handle_plan_selection, pattern="^select_plan_")
            ],
            USER_PAYMENT_UPLOAD: [
                CommandHandler("plan", plan_command),
                CallbackQueryHandler(show_plans_list, pattern="^select_plans_menu$"),
                MessageHandler(filters.PHOTO, receive_payment_screenshot),
                CallbackQueryHandler(handle_payment_upload_back, pattern="^back_to_plans$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_user_flow)]
    )

    return [
        CommandHandler("start", start_command),
        plan_conv
    ]
