"""
Application bootstrap.

Cross-cutting startup concerns that don't belong to any single layer:
logging configuration (`logging.py`) and the app lifespan/startup-shutdown
hooks (`events.py`). Imported once from `main.py`.
"""
