import gettext as gettext_module
import os

DOMAIN = "msGait"  # Domain definition
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALES_DIR = os.path.join(BASE_DIR, '..', 'locales')

_translation = None

def init_translation(idioma='es'):
    global _translation
    try:
        _translation = gettext_module.translation(DOMAIN, LOCALES_DIR, languages=[idioma])
        _translation.install() # This installs _() globally *dentro de este módulo*
    except FileNotFoundError:
        _translation = gettext_module.NullTranslations() # Null translation if not found
        global _
        _ = lambda s: s # Defining _ locally in this case

def gettext(*args, **kwargs):
    if _translation:
        return _translation.gettext(*args, **kwargs)
    return args[0] if args else ''

_ = gettext # Alias for translation function

