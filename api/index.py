import os
import sys

# Ensure repository root is importable when Vercel runs from /var/task/api.
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from culture_app import app  # noqa: E402

# 일부 WSGI 게이트웨이 호환
application = app

