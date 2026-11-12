import yaml
from .settings import BASE
CONFIG = yaml.safe_load((BASE / 'config/crops.yaml').read_text(encoding='utf-8'))
