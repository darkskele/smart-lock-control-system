"""
application.state_manager

State management component, manages state of all devices and provides interfaces to interact with them.
"""

from .lock_state_manager import LockManager

__all__ = ["LockManager"]
