"""
OCPP 충전소 시뮬레이터 GUI - 유틸리티 함수
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

# 설정 파일 경로
CONFIG_FILE = "ocpp_gui_config.json"

def save_config(config: Dict[str, Any]) -> bool:
    """설정 저장"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"설정 저장 오류: {e}")
        return False

def load_config() -> Optional[Dict[str, Any]]:
    """설정 불러오기"""
    if not os.path.exists(CONFIG_FILE):
        return None
        
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"설정 불러오기 오류: {e}")
        return None

def format_timestamp(timestamp: Optional[float] = None) -> str:
    """타임스탬프 포맷팅"""
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

def format_power(power_value: float) -> str:
    """전력 값 포맷팅"""
    if power_value >= 1000:
        return f"{power_value/1000:.2f} kW"
    return f"{power_value:.0f} W"

def parse_power(power_str: str) -> float:
    """전력 문자열 파싱"""
    power_str = power_str.strip().lower()
    if power_str.endswith("kw"):
        return float(power_str[:-2]) * 1000
    elif power_str.endswith("w"):
        return float(power_str[:-1])
    else:
        return float(power_str)
