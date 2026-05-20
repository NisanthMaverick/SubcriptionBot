from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def build_grid_keyboard(buttons: list, back_button: InlineKeyboardButton = None) -> InlineKeyboardMarkup:
    """
    Arranges a list of main InlineKeyboardButtons in a 2-button-per-row grid.
    If there is an odd number of main buttons, the last one stays on its own row.
    If a back/footer button is provided, it is added as a single full-width button at the very bottom.
    """
    keyboard = []
    
    # Process main buttons in chunks of 2
    for i in range(0, len(buttons), 2):
        keyboard.append(buttons[i:i+2])
        
    # Append the back button on its own single row
    if back_button:
        keyboard.append([back_button])
        
    return InlineKeyboardMarkup(keyboard)
