"""
OCPP 충전소 시뮬레이터 - Enum 정의
"""

from enum import Enum

class EventType(Enum):
    STARTED = "Started"
    UPDATED = "Updated"
    ENDED = "Ended"

class TriggerReason(Enum):
    CABLE_PLUGGED_IN = "CablePluggedIn"
    METER_VALUE_PERIODIC = "MeterValuePeriodic"
    EV_DISCONNECTED = "EVDisconnected"

class ConnectorStatus(Enum):
    AVAILABLE = "Available"
    OCCUPIED = "Occupied"
    UNAVAILABLE = "Unavailable"
