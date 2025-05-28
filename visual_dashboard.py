"""
OCPP 충전소 시뮬레이터 GUI - 시각적 대시보드 모듈
"""

import tkinter as tk
from tkinter import ttk
import time
import math

class PowerMeter(tk.Canvas):
    """전력 미터 위젯"""
    
    def __init__(self, parent, width=200, height=100, max_power=7000):
        super().__init__(parent, width=width, height=height, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.width = width
        self.height = height
        self.max_power = max_power
        self.current_power = 0
        self.draw_meter()
        
    def draw_meter(self):
        """미터 기본 구조 그리기"""
        # Clear canvas
        self.delete("all")
        
        # Draw background
        self.create_rectangle(0, 0, self.width, self.height, fill="white", outline="")
        
        # Draw scale
        scale_width = self.width - 20
        scale_height = 20
        scale_x = 10
        scale_y = self.height - 30
        
        self.create_rectangle(scale_x, scale_y, scale_x + scale_width, scale_y + scale_height, 
                             fill="#f0f0f0", outline="#cccccc")
        
        # Draw scale markers
        for i in range(11):
            x = scale_x + (scale_width * i / 10)
            marker_height = 5 if i % 5 == 0 else 3
            self.create_line(x, scale_y, x, scale_y + marker_height, fill="#666666")
            if i % 5 == 0:
                power_value = int(self.max_power * i / 10)
                self.create_text(x, scale_y + scale_height + 10, text=f"{power_value}W", font=("Arial", 8))
        
        # Draw power bar
        power_ratio = min(1.0, self.current_power / self.max_power)
        bar_width = scale_width * power_ratio
        
        # Determine color based on power level
        if power_ratio < 0.3:
            color = "#4CAF50"  # Green
        elif power_ratio < 0.7:
            color = "#FFC107"  # Yellow
        else:
            color = "#F44336"  # Red
            
        self.create_rectangle(scale_x, scale_y, scale_x + bar_width, scale_y + scale_height, 
                             fill=color, outline="")
        
        # Draw power value
        self.create_text(self.width / 2, 15, text=f"현재 전력: {self.current_power}W", 
                        font=("Arial", 10, "bold"))
        
    def update_power(self, power):
        """전력값 업데이트"""
        self.current_power = power
        self.draw_meter()

class ChargerStatusIndicator(tk.Canvas):
    """충전기 상태 표시 위젯"""
    
    def __init__(self, parent, width=200, height=200):
        super().__init__(parent, width=width, height=height, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.width = width
        self.height = height
        self.status = "Available"
        self.draw_indicator()
        
    def draw_indicator(self):
        """상태 표시기 그리기"""
        # Clear canvas
        self.delete("all")
        
        # Draw background
        self.create_rectangle(0, 0, self.width, self.height, fill="white", outline="")
        
        # Draw charger icon
        self.draw_charger_icon()
        
        # Draw status text
        status_colors = {
            "Available": "#4CAF50",  # Green
            "Occupied": "#FFC107",   # Yellow
            "Unavailable": "#F44336" # Red
        }
        
        status_color = status_colors.get(self.status, "#666666")
        
        # Draw status circle
        self.create_oval(self.width - 40, 10, self.width - 10, 40, 
                        fill=status_color, outline="")
        
        # Draw status text with Korean translation
        status_text = self.status
        if status_text == "Available":
            status_text = "사용 가능"
        elif status_text == "Occupied":
            status_text = "이용중"
        elif status_text == "Unavailable":
            status_text = "사용 불가"
            
        self.create_text(self.width / 2, self.height - 20, 
                        text=f"상태: {status_text}", 
                        font=("Arial", 10, "bold"),
                        fill=status_color)
        
    def draw_charger_icon(self):
        """충전기 아이콘 그리기"""
        # Draw charger base
        center_x = self.width / 2
        center_y = self.height / 2 - 10
        
        # Draw charger body
        self.create_rectangle(center_x - 30, center_y - 40, 
                             center_x + 30, center_y + 40, 
                             fill="#e0e0e0", outline="#666666", width=2)
        
        # Draw charger screen
        self.create_rectangle(center_x - 20, center_y - 30, 
                             center_x + 20, center_y - 10, 
                             fill="#333333", outline="")
        
        # Draw connector
        self.create_rectangle(center_x - 10, center_y + 40, 
                             center_x + 10, center_y + 60, 
                             fill="#333333", outline="")
        
        # Draw cable
        if self.status == "Occupied":
            # Draw wavy cable when occupied
            cable_points = []
            for i in range(21):
                x = center_x + (i - 10) * 2
                y = center_y + 70 + math.sin(i / 3) * 10
                cable_points.extend([x, y])
            
            self.create_line(*cable_points, fill="#333333", width=3, smooth=True)
            
            # Draw plug
            self.create_rectangle(center_x + 20, center_y + 65, 
                                 center_x + 40, center_y + 85, 
                                 fill="#666666", outline="")
        else:
            # Draw straight cable when not occupied
            self.create_line(center_x, center_y + 60, center_x, center_y + 80, 
                            fill="#333333", width=3)
            
            # Draw plug
            self.create_rectangle(center_x - 10, center_y + 80, 
                                 center_x + 10, center_y + 100, 
                                 fill="#666666", outline="")
        
    def update_status(self, status):
        """상태 업데이트"""
        self.status = status
        self.draw_indicator()

class ChargerVisualFrame(ttk.LabelFrame):
    """충전기 시각화 프레임"""
    
    def __init__(self, parent, charger_id):
        super().__init__(parent, text=f"충전기 {charger_id}", padding="10")
        self.charger_id = charger_id
        
        # Create layout
        self.create_widgets()
        
    def create_widgets(self):
        """위젯 생성"""
        # Create two columns
        left_frame = ttk.Frame(self)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        right_frame = ttk.Frame(self)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Left column: Status indicator
        self.status_indicator = ChargerStatusIndicator(left_frame)
        self.status_indicator.pack(fill=tk.BOTH, expand=True)
        
        # Right column: Power meter and info
        self.power_meter = PowerMeter(right_frame)
        self.power_meter.pack(fill=tk.X, pady=(0, 10))
        
        # Info frame
        info_frame = ttk.LabelFrame(right_frame, text="충전 정보", padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        # Status info
        status_frame = ttk.Frame(info_frame)
        status_frame.pack(fill=tk.X, pady=2)
        
        status_label = ttk.Label(status_frame, text="상태:", width=10)
        status_label.pack(side=tk.LEFT)
        
        self.status_var = tk.StringVar(value="사용 가능")
        status_value = ttk.Label(status_frame, textvariable=self.status_var)
        status_value.pack(side=tk.LEFT)
        
        # Power info
        power_frame = ttk.Frame(info_frame)
        power_frame.pack(fill=tk.X, pady=2)
        
        power_label = ttk.Label(power_frame, text="전력:", width=10)
        power_label.pack(side=tk.LEFT)
        
        self.power_var = tk.StringVar(value="0 W")
        power_value = ttk.Label(power_frame, textvariable=self.power_var)
        power_value.pack(side=tk.LEFT)
        
        # Total price info
        price_frame = ttk.Frame(info_frame)
        price_frame.pack(fill=tk.X, pady=2)
        
        price_label = ttk.Label(price_frame, text="총 금액:", width=10)
        price_label.pack(side=tk.LEFT)
        
        self.total_price_var = tk.StringVar(value="-")
        price_value = ttk.Label(price_frame, textvariable=self.total_price_var, font=("Arial", 10, "bold"))
        price_value.pack(side=tk.LEFT)
        
        # Last updated info
        update_frame = ttk.Frame(info_frame)
        update_frame.pack(fill=tk.X, pady=2)
        
        update_label = ttk.Label(update_frame, text="최종 갱신:", width=10)
        update_label.pack(side=tk.LEFT)
        
        self.update_var = tk.StringVar(value="-")
        update_value = ttk.Label(update_frame, textvariable=self.update_var)
        update_value.pack(side=tk.LEFT)
        
    def update_status(self, status):
        """상태 업데이트"""
        # Convert status to Korean for display
        status_text = status
        if status == "Available":
            status_text = "사용 가능"
        elif status == "Occupied":
            status_text = "이용중"
        elif status == "Unavailable":
            status_text = "사용 불가"
            
        self.status_var.set(status_text)
        self.status_indicator.update_status(status)
        self.update_var.set(time.strftime('%H:%M:%S'))
        
    def update_power(self, power):
        """전력 업데이트"""
        self.power_var.set(f"{power} W")
        self.power_meter.update_power(power)
        self.update_var.set(time.strftime('%H:%M:%S'))
        
    def update_total_price(self, total_price):
        """총 금액 정보 업데이트"""
        if total_price is not None:
            self.total_price_var.set(f"{total_price}원")
            
            # 상태가 Available이 아니면 사용 가능으로 변경 (충전 완료 시)
            if self.status_var.get() != "사용 가능":
                self.update_status("Available")
                
            # 현재 시간 업데이트
            self.update_var.set(time.strftime('%H:%M:%S'))
        else:
            self.total_price_var.set("-")
