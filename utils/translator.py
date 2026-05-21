from deep_translator import GoogleTranslator
from functools import lru_cache

@lru_cache(maxsize=1024)
def _do_translate(text: str, target_lang: str) -> str:
    try:
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return translated if translated else text
    except Exception:
        # Graceful fallback on network or API failure
        return text

def translate_text(text: str, target_lang: str) -> str:
    """
    Translates text to the target language code. If target_lang is 'en', None, or invalid,
    returns the original text.
    """
    if not target_lang or target_lang.lower().startswith('en'):
        return text

    # Extract primary language subtag (e.g., 'en-US' -> 'en')
    lang = target_lang.split('-')[0].lower()
    
    return _do_translate(text, lang)
