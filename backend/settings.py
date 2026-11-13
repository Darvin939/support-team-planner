"""Load instance configuration before importing persistence or application modules."""

import os

from dotenv import load_dotenv


if os.environ.get('SUPPORT_PLANNER_SKIP_DOTENV') != '1':
    env_file = os.environ.get('SUPPORT_PLANNER_ENV_FILE')
    if env_file is None:
        load_dotenv(override=False)
    else:
        try:
            with open(env_file, encoding='utf-8') as stream:
                load_dotenv(stream=stream, override=False, interpolate=False)
        except (OSError, UnicodeError):
            raise RuntimeError('Unable to read SUPPORT_PLANNER_ENV_FILE as a UTF-8 dotenv file') from None
