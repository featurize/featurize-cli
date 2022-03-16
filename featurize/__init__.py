import sys
import os
from json import JSONDecodeError
from .featurize_client import FeaturizeClient


def _find_token():
    token_from_env = os.getenv('FEATURIZE_API_TOKEN')
    cfg_file = os.getenv('FEATURIZE_CFG_FILE', '/etc/featurize_token.txt')
    if token_from_env:
        return token_from_env
    try:
        with open(cfg_file, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return None
    except JSONDecodeError:
        sys.exit(f'config file {cfg_file} parse error')


def _find_instance_id():
    return os.getenv('FEATURIZE_INSTANCE_ID')


def create_client_from_env():
    token = _find_token()
    instance_id = _find_instance_id()
    if token is None:
        sys.exit('Token is missed')
    return FeaturizeClient(token=token, instance_id=instance_id)


__version__ = '0.0.22'
__all__ = ['FeaturizeClient', 'create_client_from_env']
