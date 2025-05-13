"""
OCPP 충전소 시뮬레이터 GUI - 메인 애플리케이션 클래스
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import threading
import time
from typing import Dict, List, Optional

from enums import ConnectorStatus
from gui_client import GuiOcppClient
from charger_windows import LoginWindow, ChargingWindow
from visual_dashboard import ChargerVisualFrame

# 상수 정의
NUM_EVSE = 3

class OcppGuiApp(tk.Tk):
    """OCPP GUI 애플리케이션 메인 클래스"""
    
    def __init__(self):
        super().__init__()
        self.title("OCPP 충전소 시뮬레이터")
        self.geometry("1000x1650")  # 원래 창 크기로 되돌림
        self.minsize(900, 650)    # 원래 최소 크기로 되돌림
        
        # Event loop for asyncio
        self.event_loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.loop_thread.start()
        
        # OCPP client
        self.ocpp_client = None
        
        # Charger windows
        self.charger_windows = {}
        
        # Charger in use status
        self.charger_in_use = [False] * NUM_EVSE
        
        # Create widgets
        self.create_widgets()
        
        # Center window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # Protocol for closing
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def _run_event_loop(self):
        """비동기 이벤트 루프 실행"""
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_forever()
        
    def create_widgets(self):
        """GUI 위젯 생성"""
        # Main frame with two columns
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left column (connection settings)
        left_frame = ttk.LabelFrame(main_frame, text="연결 설정", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5), ipadx=5, ipady=5)
        
        # WebSocket URL
        ws_frame = ttk.Frame(left_frame)
        ws_frame.pack(fill=tk.X, pady=5)
        
        ws_label = ttk.Label(ws_frame, text="WebSocket URL:")
        ws_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.ws_entry = ttk.Entry(ws_frame)
        self.ws_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.ws_entry.insert(0, "ws://localhost:8080/ocpp")
        
        # Serial port
        serial_frame = ttk.Frame(left_frame)
        serial_frame.pack(fill=tk.X, pady=5)
        
        serial_label = ttk.Label(serial_frame, text="시리얼 포트:")
        serial_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.serial_entry = ttk.Entry(serial_frame)
        self.serial_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Use serial checkbox
        self.use_serial_var = tk.BooleanVar(value=False)
        use_serial_check = ttk.Checkbutton(
            left_frame, 
            text="시리얼 포트 사용 (체크 해제시 수동 모드)", 
            variable=self.use_serial_var
        )
        use_serial_check.pack(fill=tk.X, pady=5)
        
        # Baud rate
        baud_frame = ttk.Frame(left_frame)
        baud_frame.pack(fill=tk.X, pady=5)
        
        baud_label = ttk.Label(baud_frame, text="Baud Rate:")
        baud_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.baud_entry = ttk.Entry(baud_frame)
        self.baud_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.baud_entry.insert(0, "2400")
        
        # Connection status
        status_frame = ttk.Frame(left_frame)
        status_frame.pack(fill=tk.X, pady=10)
        
        status_label = ttk.Label(status_frame, text="상태:")
        status_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_var = tk.StringVar(value="연결 안됨")
        self.status_indicator = ttk.Label(status_frame, textvariable=self.status_var, foreground="red")
        self.status_indicator.pack(side=tk.LEFT)
        
        # Connect/Disconnect button
        self.connect_button = ttk.Button(left_frame, text="WebSocket 연결", command=self.toggle_connection)
        self.connect_button.pack(fill=tk.X, pady=5)
        
        # Charger buttons
        charger_frame = ttk.LabelFrame(left_frame, text="충전기", padding="10")
        charger_frame.pack(fill=tk.X, pady=10)
        
        for i in range(1, NUM_EVSE + 1):
            charger_button = ttk.Button(
                charger_frame,
                text=f"충전기 {i}",
                command=lambda idx=i: self.open_charger(idx)
            )
            charger_button.pack(fill=tk.X, pady=5)
            
        # Right column (content)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Create notebook for tabbed content
        self.content_notebook = ttk.Notebook(right_frame)
        self.content_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create visual dashboard tab
        visual_tab = ttk.Frame(self.content_notebook)
        self.content_notebook.add(visual_tab, text="시각화 대시보드")
        
        # Create visual dashboard
        self.visual_dashboard = ttk.Frame(visual_tab, padding="10")
        self.visual_dashboard.pack(fill=tk.BOTH, expand=True)
        
        # Create visual frames for each charger
        self.charger_visuals = []
        for i in range(1, NUM_EVSE + 1):
            visual_frame = ChargerVisualFrame(self.visual_dashboard, i)
            visual_frame.pack(fill=tk.BOTH, expand=True, pady=10)  # 원래의 세로 배치로 되돌림
            self.charger_visuals.append(visual_frame)
        
        # Create log tab
        log_tab = ttk.Frame(self.content_notebook)
        self.content_notebook.add(log_tab, text="로그")
        
        # Create log notebook
        self.log_notebook = ttk.Notebook(log_tab)
        self.log_notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create a tab for all logs
        all_logs_frame = ttk.Frame(self.log_notebook)
        self.log_notebook.add(all_logs_frame, text="전체 로그")
        
        # All logs text area
        self.log_text = scrolledtext.ScrolledText(all_logs_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Create individual log tabs for each charger
        self.charger_logs = []
        for i in range(1, NUM_EVSE + 1):
            charger_frame = ttk.Frame(self.log_notebook)
            self.log_notebook.add(charger_frame, text=f"충전기 {i} 로그")
            
            charger_log = scrolledtext.ScrolledText(charger_frame, wrap=tk.WORD)
            charger_log.pack(fill=tk.BOTH, expand=True)
            self.charger_logs.append(charger_log)
        
        # Charger status frame
        charger_status_frame = ttk.LabelFrame(log_tab, text="충전기 상태", padding="10")
        charger_status_frame.pack(fill=tk.X, pady=5)
        
        # Charger status indicators
        self.charger_status_vars = []
        self.charger_power_vars = []
        
        for i in range(1, NUM_EVSE + 1):
            status_row = ttk.Frame(charger_status_frame)
            status_row.pack(fill=tk.X, pady=2)
            
            charger_label = ttk.Label(status_row, text=f"충전기 {i}:", width=10)
            charger_label.pack(side=tk.LEFT, padx=(0, 5))
            
            status_var = tk.StringVar(value="Available")
            status_label = ttk.Label(status_row, textvariable=status_var, width=10)
            status_label.pack(side=tk.LEFT, padx=(0, 5))
            self.charger_status_vars.append(status_var)
            
            power_var = tk.StringVar(value="0 W")
            power_label = ttk.Label(status_row, textvariable=power_var)
            power_label.pack(side=tk.LEFT)
            self.charger_power_vars.append(power_var)
            
    def log(self, message):
        """로그 메시지 추가"""
        timestamp = time.strftime('%H:%M:%S')
        log_entry = f"{timestamp} - {message}\n"
        
        # Add to main log
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # Check if message is related to a specific charger
        for i in range(1, NUM_EVSE + 1):
            if f"EVSE {i}:" in message or f"충전기 {i}" in message:
                self.charger_logs[i-1].insert(tk.END, log_entry)
                self.charger_logs[i-1].see(tk.END)
                break
        
        # Add power data logs to all charger logs
        if message.startswith("W:"):
            values = message.split()
            if len(values) >= NUM_EVSE + 1:  # "W:" + at least NUM_EVSE values
                for i in range(NUM_EVSE):
                    if i + 1 < len(values):
                        power_log = f"{timestamp} - 전력: {values[i+1]}W\n"
                        self.charger_logs[i].insert(tk.END, power_log)
                        self.charger_logs[i].see(tk.END)
            
    def update_charger_status(self, charger_id, status):
        """충전기 상태 업데이트"""
        if 1 <= charger_id <= NUM_EVSE:
            self.charger_status_vars[charger_id - 1].set(status)
            # Update visual dashboard
            self.charger_visuals[charger_id - 1].update_status(status)
            
            # Update charger in use status
            self.charger_in_use[charger_id - 1] = (status == "Occupied")
            
    def update_power_display(self, charger_id, power_value):
        """충전기 전력 표시 업데이트"""
        if 1 <= charger_id <= NUM_EVSE:
            self.charger_power_vars[charger_id - 1].set(f"{power_value} W")
            # Update visual dashboard
            self.charger_visuals[charger_id - 1].update_power(power_value)
            
            # Update status based on power
            if power_value > 0:
                if not self.charger_in_use[charger_id - 1]:
                    self.update_charger_status(charger_id, "Occupied")
                    self.log(f"충전기 {charger_id}: 전력 감지로 상태가 '이용중'으로 변경되었습니다.")
            else:
                if self.charger_in_use[charger_id - 1]:
                    self.update_charger_status(charger_id, "Available")
                    self.log(f"충전기 {charger_id}: 전력이 없어 상태가 '사용 가능'으로 변경되었습니다.")
            
            # Also update the charger window if open
            if charger_id in self.charger_windows and self.charger_windows[charger_id].winfo_exists():
                self.charger_windows[charger_id].update_power_display(power_value)
                
    def toggle_connection(self):
        """연결/해제 토글"""
        if not self.ocpp_client or not self.ocpp_client.running:
            # Connect
            websocket_url = self.ws_entry.get()
            
            serial_port = None
            if self.use_serial_var.get():
                serial_port = self.serial_entry.get()
                
            try:
                baud_rate = int(self.baud_entry.get())
            except ValueError:
                baud_rate = 2400
                self.baud_entry.delete(0, tk.END)
                self.baud_entry.insert(0, str(baud_rate))
                
            self.connect_button.config(text="연결 중...", state=tk.DISABLED)
            
            # Create OCPP client
            self.ocpp_client = GuiOcppClient(self, websocket_url, serial_port, baud_rate)
            
            # Start client in event loop
            asyncio.run_coroutine_threadsafe(self.ocpp_client.run_loop(), self.event_loop)
            
            # Update UI
            self.status_var.set("연결됨")
            self.status_indicator.config(foreground="green")
            self.connect_button.config(text="연결 해제", state=tk.NORMAL)
            
        else:
            # Disconnect
            if self.ocpp_client:
                self.ocpp_client.stop()
                
            # Close all charger windows
            for window in self.charger_windows.values():
                if window.winfo_exists():
                    window.destroy()
            self.charger_windows.clear()
                
            # Update UI
            self.status_var.set("연결 안됨")
            self.status_indicator.config(foreground="red")
            self.connect_button.config(text="WebSocket 연결", state=tk.NORMAL)
            
            # Reset visual dashboard
            for visual in self.charger_visuals:
                visual.update_status("Available")
                visual.update_power(0)
                
            # Reset charger in use status
            self.charger_in_use = [False] * NUM_EVSE
            
    def open_charger(self, charger_id):
        """충전기 창 열기"""
        if not self.ocpp_client or not self.ocpp_client.running:
            messagebox.showerror("오류", "먼저 WebSocket을 연결해주세요")
            return
        
        # Check if charger is in use
        if self.charger_in_use[charger_id - 1]:
            messagebox.showinfo("충전기 사용중", f"충전기 {charger_id}는 현재 사용중입니다.")
            return
        
        # First show login window
        LoginWindow(self, charger_id, lambda: self.on_login_success(charger_id), 
                self.ocpp_client, self.event_loop)
        
    def on_login_success(self, charger_id):
        """로그인 성공 후 충전기 창 열기"""
        # Open or focus the charger window
        if charger_id in self.charger_windows and self.charger_windows[charger_id].winfo_exists():
            self.charger_windows[charger_id].focus_force()
        else:
            self.charger_windows[charger_id] = ChargingWindow(
                self, 
                charger_id, 
                self.ocpp_client,
                self.event_loop
            )
            
    def on_closing(self):
        """애플리케이션 종료 처리"""
        # Stop OCPP client
        if self.ocpp_client:
            self.ocpp_client.stop()
            
        # Stop event loop
        self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        
        # Wait for thread to finish
        if self.loop_thread.is_alive():
            self.loop_thread.join(timeout=1.0)
            
        # Destroy window
        self.destroy()
