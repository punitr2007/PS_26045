import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
code_dir = os.path.dirname(backend_dir)
ingestion_dir = os.path.join(code_dir, "ingestion")
if os.path.exists(ingestion_dir) and ingestion_dir not in sys.path:
    sys.path.insert(0, ingestion_dir)
