# src/services/order_models.py

from pydantic import BaseModel

class OrderIn(BaseModel):
    # Common request model for placing an order.
    # This is reused by:
    #   src/services/fast_stats_user.py       (JSON version)
    #   src/services/fast_stats_user_avro.py  (Avro version)
    user: str
    total: float
    status: str = "PLACED"
