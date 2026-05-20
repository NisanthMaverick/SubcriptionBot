# Master Admin Handler Aggregator
from telegram.ext import (
    CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters
)
from handlers.admin_modules import (
    ADD_PLAN_NAME, ADD_PLAN_DESC, ADD_PLAN_DURATIONS, ADD_DURATION_INPUT,
    PAY_UPI, PAY_QR, PAY_VALIDITY, LOG_CHAN_ID,
    EDIT_PLAN_TITLE, EDIT_PLAN_DESC, EDIT_PLAN_LINK,
    SUB_REVOKE_REASON, GRANT_USER_ID, GRANT_PLAN, GRANT_DURATION, GRANT_CUSTOM,
    WELCOME_EDIT_TEXT, WELCOME_ADD_BTN, PLAN_ADD_EXT_BTN, ADMIN_BROADCAST, ADMIN_ADD_DB
)
from handlers.admin_modules.menu import (
    admin_start, settings_command, show_main_menu,
    cancel_admin_flow, cancel_callback_handler, handle_menu_navigation
)
from handlers.admin_modules.plans import (
    start_add_plan, receive_plan_name, receive_plan_desc,
    handle_durations_menu_click, receive_duration_input
)
from handlers.admin_modules.plans_edit import (
    handle_edit_plan_selection, start_edit_title, receive_edited_title,
    start_edit_desc, receive_edited_desc, start_edit_link,
    receive_edited_link, start_edit_durations
)
from handlers.admin_modules.payment import (
    start_add_upi, receive_upi, start_setup_qr,
    receive_qr, start_setup_validity, receive_validity
)
from handlers.admin_modules.subs_manage import (
    start_revoke_sub, receive_revoke_reason, list_plan_subscribers_callback,
    manage_subscriber_callback, download_doc_callback, admin_send_link_callback,
    admin_send_ind_links_callback
)
from handlers.admin_modules.subs_grant import (
    grant_start, receive_grant_user_id, handle_grant_plan,
    handle_grant_duration, receive_grant_custom
)
from handlers.admin_modules.config import (
    start_welcome_edit_text, receive_welcome_edit_text,
    start_welcome_add_btn, receive_welcome_add_btn, start_ep_extbtn,
    receive_ep_extbtn, start_log_channel, receive_log_channel,
    expiry_notify_settings, handle_expiry_notify_callbacks,
    export_bot_settings, settings_import_conv
)
from handlers.admin_modules.cluster import (
    start_broadcast, receive_broadcast, start_add_db, receive_add_db
)
from handlers.admin_modules.channel_mapping import channel_add_conv, channel_nav_handlers
from handlers.admin_modules.raid import raid_timeout_conv, raid_chan_conv, raid_interval_conv, raid_action_handlers

def get_admin_handlers() -> list:
    add_plan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_plan, pattern="^admin_add_plan$")],
        states={
            ADD_PLAN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_plan_name)],
            ADD_PLAN_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_plan_desc)],
            ADD_PLAN_DURATIONS: [CallbackQueryHandler(handle_durations_menu_click, pattern="^(add_dur_btn|confirm_save_plan|cancel_add_plan)$")],
            ADD_DURATION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_duration_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^cancel_")]
    )

    edit_title_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_title, pattern="^ep_title_")],
        states={EDIT_PLAN_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edited_title)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^menu_plans")]
    )

    edit_desc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_desc, pattern="^ep_desc_")],
        states={EDIT_PLAN_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edited_desc)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^menu_plans")]
    )

    edit_link_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_link, pattern="^ep_link_")],
        states={EDIT_PLAN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edited_link)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^list_edit_plans")]
    )

    edit_dur_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_edit_durations, pattern="^ep_dur_")],
        states={
            ADD_PLAN_DURATIONS: [CallbackQueryHandler(handle_durations_menu_click, pattern="^(add_dur_btn|confirm_save_plan|cancel_add_plan)$")],
            ADD_DURATION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_duration_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^cancel_")]
    )

    payment_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_upi, pattern="^add_upi_id$"),
            CallbackQueryHandler(start_setup_qr, pattern="^setup_qr_code$"),
            CallbackQueryHandler(start_setup_validity, pattern="^setup_validity$")
        ],
        states={
            PAY_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_upi)],
            PAY_QR: [MessageHandler(filters.PHOTO, receive_qr)],
            PAY_VALIDITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_validity)]
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^menu_payment")]
    )

    log_channel_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_log_channel, pattern="^admin_log_channel$")],
        states={
            LOG_CHAN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_log_channel)]
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^cancel_")]
    )

    sub_revoke_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_revoke_sub, pattern="^sub_rem_")],
        states={SUB_REVOKE_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_revoke_reason)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^menu_subs")]
    )

    grant_sub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(grant_start, pattern="^grant_start$")],
        states={
            GRANT_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_grant_user_id)],
            GRANT_PLAN: [CallbackQueryHandler(handle_grant_plan, pattern="^gplan_")],
            GRANT_DURATION: [CallbackQueryHandler(handle_grant_duration, pattern="^gdur_")],
            GRANT_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_grant_custom)]
        },
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^menu_subs")]
    )

    welcome_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_welcome_edit_text, pattern="^welcome_edit_text$")],
        states={WELCOME_EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_welcome_edit_text)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^welcome_config_menu")]
    )

    welcome_addbtn_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_welcome_add_btn, pattern="^welcome_add_btn$")],
        states={WELCOME_ADD_BTN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_welcome_add_btn)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^welcome_config_menu")]
    )

    plan_extbtn_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_ep_extbtn, pattern="^ep_extbtn_")],
        states={PLAN_ADD_EXT_BTN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ep_extbtn)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^list_edit_plans")]
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_broadcast, pattern="^menu_broadcast$")],
        states={ADMIN_BROADCAST: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_broadcast)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^menu_main")]
    )

    add_db_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_db, pattern="^add_db_url$")],
        states={ADMIN_ADD_DB: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_db)]},
        fallbacks=[CommandHandler("cancel", cancel_admin_flow), CallbackQueryHandler(cancel_callback_handler, pattern="^menu_db_mgr")]
    )

    return [
        CommandHandler("settings", settings_command),
        add_plan_conv,
        edit_title_conv,
        edit_desc_conv,
        edit_link_conv,
        edit_dur_conv,
        payment_conv,
        log_channel_conv,
        sub_revoke_conv,
        grant_sub_conv,
        welcome_edit_conv,
        welcome_addbtn_conv,
        plan_extbtn_conv,
        broadcast_conv,
        add_db_conv,
        channel_add_conv,
        raid_timeout_conv,
        raid_chan_conv,
        raid_interval_conv,
        settings_import_conv,
        CallbackQueryHandler(handle_menu_navigation, pattern="^(menu_main|menu_plans|menu_payment|menu_subs|menu_config|menu_status|menu_db_mgr|menu_db_clean|close_panel|list_|reset_upi_ids|db_warn_|db_exec_|del_plan_|welcome_|ep_resext_|chan_menu|raid_menu|menu_backup_restore)"),
        CallbackQueryHandler(handle_edit_plan_selection, pattern="^edit_plan_"),
        CallbackQueryHandler(expiry_notify_settings, pattern="^admin_expiry_notify$"),
        CallbackQueryHandler(handle_expiry_notify_callbacks, pattern="^set_exp_"),
        CallbackQueryHandler(list_plan_subscribers_callback, pattern="^admin_plan_subs_"),
        CallbackQueryHandler(manage_subscriber_callback, pattern="^admin_manage_sub_"),
        CallbackQueryHandler(download_doc_callback, pattern="^admin_download_doc$"),
        CallbackQueryHandler(admin_send_link_callback, pattern="^admin_send_link_"),
        CallbackQueryHandler(admin_send_ind_links_callback, pattern="^admin_send_ind_links_"),
        CallbackQueryHandler(export_bot_settings, pattern="^admin_export_settings$")
    ] + channel_nav_handlers + raid_action_handlers
