"""Atomic public evaluation receipts, tolerating brief Windows reader/AV locks."""
import json
import os
from pathlib import Path
import time
from uuid import uuid4


def atomic_json(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.'+str(uuid4())+'.pending')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    deadline=time.monotonic()+10
    try:
        while True:
            try:os.replace(temporary,path);return
            except PermissionError:
                if time.monotonic()>=deadline:raise
                time.sleep(.05)
    finally:temporary.unlink(missing_ok=True)
