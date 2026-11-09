"""Load instance configuration before importing persistence or application modules."""

from dotenv import load_dotenv
import os

if os.environ.get('SUPPORT_PLANNER_SKIP_DOTENV') != '1':
    load_dotenv(override=False)
