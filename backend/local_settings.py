"""Local-user key persistence, never included in static assets or generated programs."""
import json,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KEY_FILE=ROOT/'.local/settings.json'

def public_mode():return os.environ.get('CONTOUR_PUBLIC','').lower() in ('1','true','yes')

def stored_key():
    if public_mode():return ''
    try:
        data=json.loads(KEY_FILE.read_text(encoding='utf-8'));key=data.get('openai_api_key','')
        return key if isinstance(key,str) else ''
    except (OSError,ValueError):return ''

def server_key():
    if public_mode():return ''
    return stored_key() or os.environ.get('OPENAI_API_KEY','')

def save_local_key(key,remember):
    if public_mode():raise ValueError('Local key storage is disabled in public mode')
    key=key.strip()
    if not remember:
        KEY_FILE.unlink(missing_ok=True);return
    if not key:
        if stored_key():return
        raise ValueError('Enter a key before enabling local key storage')
    if len(key)>512 or any(c.isspace() for c in key):raise ValueError('Use a single API key without whitespace')
    KEY_FILE.parent.mkdir(exist_ok=True)
    temporary=KEY_FILE.with_suffix('.tmp')
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w',encoding='utf-8') as stream:json.dump({'openai_api_key':key},stream)
    temporary.replace(KEY_FILE)
