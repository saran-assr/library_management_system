import os
import sys
import shutil
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Vercel Serverless Filesystem Adapter:
# Vercel lambda execution environments have a read-only filesystem except for /tmp.
# If running on Vercel, copy the pre-seeded instance/library.db to /tmp/library.db if not already there.
is_vercel = os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")

if is_vercel:
    tmp_db_path = Path("/tmp/library.db")
    src_db = ROOT_DIR / "instance" / "library.db"
    if src_db.exists():
        if not tmp_db_path.exists() or src_db.stat().st_mtime > tmp_db_path.stat().st_mtime:
            shutil.copy2(src_db, tmp_db_path)
    elif not tmp_db_path.exists():
        from seed import seed_database
        seed_database(str(tmp_db_path))

    os.environ["DATABASE_PATH"] = str(tmp_db_path)

from app import create_app
from config import ProductionConfig

# Vercel Python runtime detects and calls 'app'
app = create_app(ProductionConfig)

if __name__ == "__main__":
    app.run()
