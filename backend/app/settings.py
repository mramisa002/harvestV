import os
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / '.env')
except ImportError:
    pass
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./harvestv.db')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
