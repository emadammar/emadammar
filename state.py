# state.py
# Active order state management (single active order per user)
# Stores activation_id from smscenter.pro and handles expiration

import time
from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class ActiveOrder:
    user_id: int
    service_name: str
    service_code: str
    price: float
    country: str
    operator: str = ""
    activation_id: Optional[str] = None  # ID from ACCESS_NUMBER
    phone: Optional[str] = None
    created_at: float = 0.0


# In-memory storage: one active order per user
_active_orders: Dict[int, ActiveOrder] = {}


def start_order(order: ActiveOrder) -> None:
    order.created_at = time.time()
    _active_orders[order.user_id] = order


def set_activation_info(user_id: int, activation_id: str, phone: Optional[str] = None) -> None:
    order = _active_orders.get(user_id)
    if not order:
        return
    order.activation_id = activation_id
    if phone:
        order.phone = phone


def get_active_order(user_id: int) -> Optional[ActiveOrder]:
    return _active_orders.get(user_id)


def has_active_order(user_id: int) -> bool:
    return user_id in _active_orders


def clear_order(user_id: int) -> None:
    if user_id in _active_orders:
        del _active_orders[user_id]


def is_expired(user_id: int, timeout_seconds: int) -> bool:
    order = _active_orders.get(user_id)
    if not order:
        return False
    return (time.time() - order.created_at) >= timeout_seconds