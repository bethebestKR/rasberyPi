"""
OCPP 충전소 시뮬레이터 - 메시지 유틸리티
"""

import uuid
from datetime import datetime

def generate_message_id() -> str:
    """고유한 메시지 ID 생성"""
    return f"msg-{uuid.uuid4().hex[:8]}"

def generate_timestamp() -> str:
    """현재 시간의 타임스탬프 생성"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000")

def generate_transaction_id(transaction_num: int) -> str:
    """트랜잭션 ID 생성"""
    return f"tx-{transaction_num:03d}"
