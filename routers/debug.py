import os
import re
from collections import deque

from fastapi import APIRouter, Depends, Query

from access_control import CurrentUser, require_bootstrap_admin

router = APIRouter(prefix='/api/debug')
LOG_PATH = 'application.log'
_SECRET_RE = re.compile(r'(?i)(password|token|cookie|secret)(\s*[=:]\s*)[^\s,;]+')
_LOG_RE = re.compile(r'^(?P<timestamp>\S+\s+\S+)\s+(?P<level>[A-Z]+)\s+(?P<logger>\S+)\s+(?P<message>.*)$')


def _safe_log(line):
    return _SECRET_RE.sub(r'\1\2[REDACTED]', line).rstrip('\n')


def _log_entry(line):
    safe = _safe_log(line)
    match = _LOG_RE.match(safe)
    if not match:
        return {'timestamp': '', 'level': 'INFO', 'logger': '', 'message': safe}
    return match.groupdict()


@router.get('/logs')
def logs(limit: int = Query(200, ge=1, le=1000), level: str = '', search: str = '', _: CurrentUser = Depends(require_bootstrap_admin)):
    if not os.path.isfile(LOG_PATH):
        return {'rows': []}
    with open(LOG_PATH, encoding='utf-8', errors='replace') as handle:
        lines = deque(handle, maxlen=limit * 4)
    rows = []
    for line in lines:
        entry = _log_entry(line)
        if level and entry['level'] != level.upper():
            continue
        if search and search.casefold() not in (entry['message'] + ' ' + entry['logger']).casefold():
            continue
        rows.append(entry)
    return {'rows': rows[-limit:]}
