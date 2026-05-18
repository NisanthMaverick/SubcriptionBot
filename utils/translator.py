from deep_translator import GoogleTranslator

def translate_text(text: str, target_lang: str) -> str:
    """
    Translates text to the target language code. If target_lang is 'en', None, or invalid,
    returns the original text.
    """
    if not target_lang or target_lang.lower().startswith('en'):
        return text

    # Extract primary language subtag (e.g., 'en-US' -> 'en')
    lang = target_lang.split('-')[0].lower()
    
    try:
        translated = GoogleTranslator(source='auto', target=lang).translate(text)
        return translated if translated else text
    except Exception:
        # Graceful fallback on network or API failure
        return text
