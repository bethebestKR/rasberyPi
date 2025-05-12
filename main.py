#!/usr/bin/env python3
"""
OCPP 충전소 시뮬레이터 GUI - 메인 실행 파일
"""

import tkinter as tk
from gui_app import OcppGuiApp

if __name__ == "__main__":
    app = OcppGuiApp()
    app.mainloop()
