"""
OCPP 충전소 시뮬레이터 GUI - 충전기 관련 창
"""

import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import random
import time
import json

class LoginWindow(tk.Toplevel):
    """로그인 창 (OCPP Authorize 사용)"""
    
    def __init__(self, parent, charger_id, on_login_success, ocpp_client, event_loop):
        super().__init__(parent)
        self.title(f"충전기 {charger_id} 로그인")
        self.geometry("300x200")
        self.resizable(False, False)
        self.charger_id = charger_id
        self.on_login_success = on_login_success
        self.ocpp_client = ocpp_client
        self.event_loop = event_loop
        
        # Center window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # Create widgets
        self.create_widgets()
        
    def create_widgets(self):
        """위젯 생성"""
        # Main frame
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text=f"충전기 {self.charger_id} 로그인", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # idToken
        idtoken_frame = ttk.Frame(main_frame)
        idtoken_frame.pack(fill=tk.X, pady=5)
        
        idtoken_label = ttk.Label(idtoken_frame, text="idToken:", width=10)
        idtoken_label.pack(side=tk.LEFT)
        
        self.idtoken_entry = ttk.Entry(idtoken_frame)
        self.idtoken_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.idtoken_entry.insert(0, "token001")  # 기본값 설정
        
        # Login button
        style = ttk.Style()
        style.configure("Login.TButton", font=("Arial", 11, "bold"))
        login_button = ttk.Button(main_frame, text="로그인", command=self.login, style="Login.TButton")
        login_button.pack(pady=20, ipadx=10, ipady=5)
        
        # Status message
        self.status_var = tk.StringVar(value="-")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="blue")
        status_label.pack(pady=5)
        
    async def authorize(self, id_token):
        """OCPP Authorize 요청 전송"""
        message_id = f"auth-{id_token[:3]}-{int(time.time())}"
        message = {
            "messageTypeId": 2,
            "messageId": message_id,
            "action": "Authorize",
            "payload": {
                "idToken": {
                    "idToken": id_token,
                    "type": "Central"
                }
            }
        }
        
        # 응답 이벤트 초기화
        self.ocpp_client.comm.response_event.clear()
        self.ocpp_client.comm.last_response = None
        
        # 메시지 전송
        success = await self.ocpp_client.comm.send_message(message)
        if not success:
            return False, "메시지 전송 실패"
            
        # 응답 대기 (최대 5초)
        try:
            await asyncio.wait_for(self.ocpp_client.comm.response_event.wait(), timeout=5.0)
            
            # 응답 확인
            if self.ocpp_client.comm.last_response:
                try:
                    response = json.loads(self.ocpp_client.comm.last_response)
                    if len(response) >= 3 and response[0] == 3 and response[1] == message_id:
                        # 응답 데이터 확인
                        response_data = response[2]
                        if "idTokenInfo" in response_data and "status" in response_data["idTokenInfo"]:
                            status = response_data["idTokenInfo"]["status"]
                            if status == "Accepted":
                                return True, "인증 성공"
                            else:
                                return False, f"인증 거부: {status}"
                        else:
                            return False, "응답 형식 오류"
                    else:
                        return False, "응답 형식 오류"
                except json.JSONDecodeError:
                    return False, "응답 파싱 오류"
                except Exception as e:
                    return False, f"응답 처리 오류: {e}"
            else:
                return False, "응답 없음"
        except asyncio.TimeoutError:
            return False, "응답 대기 시간 초과"
        
    def login(self):
        """로그인 처리"""
        id_token = self.idtoken_entry.get()
        
        if not id_token:
            messagebox.showerror("로그인 오류", "idToken을 입력해주세요")
            return
            
        self.status_var.set("인증 중...")
        self.update()
        
        # 비동기 인증 처리
        async def process_login():
            success, message = await self.authorize(id_token)
            
            # GUI 업데이트는 메인 스레드에서 수행
            self.after(0, lambda: self.handle_login_result(success, message))
            
        # 이벤트 루프에서 실행
        asyncio.run_coroutine_threadsafe(process_login(), self.event_loop)
        
    def handle_login_result(self, success, message):
        """로그인 결과 처리"""
        self.status_var.set(message)
        
        if success:
            # 잠시 후 창 닫고 다음 화면으로 이동
            self.after(1000, lambda: self.on_success())
        else:
            # 오류 메시지 표시
            self.status_var.set(f"오류: {message}")
            
    def on_success(self):
        """인증 성공 후 처리"""
        self.destroy()
        self.on_login_success()

class ChargingWindow(tk.Toplevel):
    """충전 제어 창"""
    
    def __init__(self, parent, charger_id, ocpp_client, event_loop):
        super().__init__(parent)
        self.title(f"충전기 {charger_id}")
        self.geometry("400x450")  # 창 크기를 더 작게 조정
        self.resizable(False, False)
        self.charger_id = charger_id
        self.ocpp_client = ocpp_client
        self.event_loop = event_loop
        self.charging = False
        self.transaction_started = False
        self.power_threshold = 100  # 충전 시작을 위한 전력 임계값 (W)
        self.power_check_timer = None
        self.last_power_value = 0
        self.ctoc_connected = False
        self.manual_mode = False
        
        # 시리얼 포트 사용 여부 확인
        self.using_serial = False
        if hasattr(self.ocpp_client, 'serial_port') and self.ocpp_client.serial_port:
            self.using_serial = True
        
        # Center window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # Create widgets
        self.create_widgets()
        
        # Protocol for closing
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start power monitoring
        self.start_power_monitoring()
        
    def create_widgets(self):
        """위젯 생성"""
        # Main frame
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text=f"충전기 {self.charger_id}", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Status
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        status_label = ttk.Label(status_frame, text="상태:", width=10, anchor="w")
        status_label.pack(side=tk.LEFT)
        
        self.status_var = tk.StringVar(value="대기중")
        status_value = ttk.Label(status_frame, textvariable=self.status_var)
        status_value.pack(side=tk.LEFT)
        
        # Price information
        price_frame = ttk.Frame(main_frame)
        price_frame.pack(fill=tk.X, pady=5)
        
        price_label = ttk.Label(price_frame, text="가격:", width=10, anchor="w")
        price_label.pack(side=tk.LEFT)
        
        self.price_var = tk.StringVar(value="10원/Wh")
        price_value = ttk.Label(price_frame, textvariable=self.price_var)
        price_value.pack(side=tk.LEFT)
        
        # Current power display
        current_power_frame = ttk.Frame(main_frame)
        current_power_frame.pack(fill=tk.X, pady=10)
        
        current_power_label = ttk.Label(current_power_frame, text="현재 전력:", width=10, anchor="w")
        current_power_label.pack(side=tk.LEFT)
        
        self.current_power_var = tk.StringVar(value="0 W")
        current_power_value = ttk.Label(current_power_frame, textvariable=self.current_power_var)
        current_power_value.pack(side=tk.LEFT)
        
        # Connection status
        connection_frame = ttk.Frame(main_frame)
        connection_frame.pack(fill=tk.X, pady=10)
        
        connection_label = ttk.Label(connection_frame, text="연결 상태:", width=10, anchor="w")
        connection_label.pack(side=tk.LEFT)
        
        self.connection_var = tk.StringVar(value="연결 대기중")
        connection_value = ttk.Label(connection_frame, textvariable=self.connection_var)
        connection_value.pack(side=tk.LEFT)
        
        # 시리얼 포트 사용 여부에 따라 수동 전력 설정 UI 표시 여부 결정
        if not self.using_serial:
            # Manual power input frame (시리얼 연결 안된 경우만 표시)
            manual_frame = ttk.LabelFrame(main_frame, text="수동 전력 설정", padding="10")
            manual_frame.pack(fill=tk.X, pady=10)
            
            # Power input
            power_frame = ttk.Frame(manual_frame)
            power_frame.pack(fill=tk.X, pady=5)
            
            power_label = ttk.Label(power_frame, text="전력 (W):", anchor="w")
            power_label.pack(side=tk.LEFT, padx=(0, 5))
            
            self.power_entry = ttk.Entry(power_frame)
            self.power_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.power_entry.insert(0, "3000")
            
            # Apply button
            apply_button = ttk.Button(
                manual_frame,
                text="전력값 적용",
                command=self.apply_manual_power
            )
            apply_button.pack(fill=tk.X, pady=5)
        else:
            # 시리얼 포트 사용 중일 때는 Entry를 만들지만 표시하지 않음 (다른 메서드에서 참조할 때 오류 방지)
            self.power_entry = ttk.Entry(main_frame)
            self.power_entry.insert(0, "3000")
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=20)
        
        # Start button
        self.start_button = tk.Button(
            buttons_frame, 
            text="충전 시작", 
            command=self.start_charging_manually,
            bg="#4CAF50",  # Green background
            fg="white",    # White text
            font=("Arial", 14, "bold"),
            height=2,
            relief=tk.RAISED,
            borderwidth=1
        )
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))
        
        # Stop button (disabled by default)
        self.stop_button = tk.Button(
            buttons_frame, 
            text="충전 중지", 
            command=self.stop_charging_manually,
            bg="#F44336",  # Red background
            fg="white",    # White text
            font=("Arial", 14, "bold"),
            height=2,
            state=tk.DISABLED,
            relief=tk.RAISED,
            borderwidth=1
        )
        self.stop_button.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(10, 0))
        
    def update_power_display(self, power_value):
        """전력 표시 업데이트"""
        self.current_power_var.set(f"{power_value} W")
        self.last_power_value = power_value
        
    def update_status(self, status):
        """상태 업데이트"""
        self.status_var.set(status)
        # 상태가 업데이트될 때 가격 정보도 함께 업데이트
        self.update_price_display()
        
    def update_connection_status(self, connected):
        """연결 상태 업데이트"""
        self.ctoc_connected = connected
        if connected:
            self.connection_var.set("연결됨")
        else:
            self.connection_var.set("연결 대기중")
        
    def update_price_display(self):
        """가격 정보 업데이트"""
        if hasattr(self.ocpp_client, 'comm') and hasattr(self.ocpp_client.comm, 'price_per_wh'):
            price = self.ocpp_client.comm.price_per_wh
            self.price_var.set(f"{price}원/Wh")
        
    def start_power_monitoring(self):
        """전력 모니터링 시작"""
        self.check_power_and_update_status()
        
    def check_power_and_update_status(self):
        """전력 확인 및 상태 업데이트"""
        # 현재 전력값 가져오기
        power_value = self.ocpp_client.power_data[self.charger_id - 1]
        
        # 전력 표시 업데이트
        self.update_power_display(power_value)
        
        # 가격 정보 업데이트
        self.update_price_display()
        
        # CTOC 연결 상태 확인 (전력이 임계값 이상이면 연결된 것으로 간주)
        connected = power_value >= self.power_threshold
        
        # 연결 상태가 변경된 경우에만 업데이트
        if connected != self.ctoc_connected:
            self.update_connection_status(connected)
            
            # CTOC가 연결되고 충전 중이 아니면 충전 시작
            if connected and not self.charging and not self.manual_mode:
                self.start_charging_auto()
            # CTOC가 연결 해제되고 충전 중이면 충전 중지
            elif not connected and self.charging and not self.manual_mode:
                self.stop_charging_auto()
            
        # 다음 확인 예약 (500ms 마다)
        self.power_check_timer = self.after(500, self.check_power_and_update_status)
        
    def apply_manual_power(self):
        """수동 전력값 적용"""
        # 시리얼 포트 사용 중인 경우 이 함수는 무시
        if self.using_serial:
            return
            
        try:
            power = float(self.power_entry.get())
            if power <= 0:
                messagebox.showerror("입력 오류", "전력은 양수여야 합니다")
                return
                
            # 전력값 설정
            idx = self.charger_id - 1
            
            # 전력값 설정 (GUI 클라이언트의 여러 배열에 모두 업데이트)
            self.ocpp_client.manual_power[idx] = power
            self.ocpp_client.power_data[idx] = power
            
            # 전압/전류 값도 업데이트 (로그에 사용되는 값)
            voltage = 220.0
            current = power / voltage
            self.ocpp_client.load3_mv[idx*2] = voltage
            self.ocpp_client.load3_mv[idx*2+1] = current
            
            # 충전 활성화 상태 설정
            self.ocpp_client.charging_active[idx] = True
            
            # 케이블 연결 상태 설정
            self.ocpp_client.cable_connected[idx] = True
            
            # 상태 업데이트
            self.update_power_display(power)
            self.update_connection_status(True)
            
            # 메시지 표시
            messagebox.showinfo("전력값 적용", f"전력값이 {power}W로 설정되었습니다.")
            
        except ValueError:
            messagebox.showerror("입력 오류", "유효한 숫자를 입력하세요")
        
    def start_charging_auto(self):
        """자동 충전 시작"""
        self.charging = True
        self.update_status("충전 중")
        
        # 트랜잭션이 아직 시작되지 않았으면 시작
        if not self.transaction_started:
            # 기본 전력값 설정 (실제 측정값 사용)
            power = max(3000, self.last_power_value)  # 최소 3000W 또는 현재 측정값
            
            # 트랜잭션 시작 이벤트 전송
            asyncio.run_coroutine_threadsafe(
                self.ocpp_client.start_charging(self.charger_id, power), 
                self.event_loop
            )
            self.transaction_started = True
            
        # 버튼 상태 업데이트 (수동 중지만 가능)
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
    def stop_charging_auto(self):
        """자동 충전 중지"""
        self.charging = False
        self.manual_mode = False
        self.update_status("대기중")
        
        # 트랜잭션이 시작되었으면 종료
        if self.transaction_started:
            # 트랜잭션 종료 이벤트 전송
            asyncio.run_coroutine_threadsafe(
                self.ocpp_client.stop_charging(self.charger_id), 
                self.event_loop
            )
            self.transaction_started = False
            
        # 버튼 상태 업데이트 (수동 시작만 가능)
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
    def start_charging_manually(self):
        """수동 충전 시작"""
        # 수동 모드로 설정
        self.manual_mode = True
        
        try:
            # 시리얼 포트 사용 여부에 따라 전력값 설정 방식 분리
            if not self.using_serial:
                # 입력된 전력값 가져오기
                power = float(self.power_entry.get())
                if power <= 0:
                    messagebox.showerror("입력 오류", "전력은 양수여야 합니다")
                    return
                    
                # 전력값 설정
                idx = self.charger_id - 1
                
                # 전력값 설정 (GUI 클라이언트의 여러 배열에 모두 업데이트)
                self.ocpp_client.manual_power[idx] = power
                self.ocpp_client.power_data[idx] = power
                
                # 전압/전류 값도 업데이트 (로그에 사용되는 값)
                voltage = 220.0
                current = power / voltage
                self.ocpp_client.load3_mv[idx*2] = voltage
                self.ocpp_client.load3_mv[idx*2+1] = current
                
                # 충전 활성화 상태 설정
                self.ocpp_client.charging_active[idx] = True
                
                # 케이블 연결 상태 설정
                self.ocpp_client.cable_connected[idx] = True
            else:
                # 시리얼 포트 사용 중인 경우 실제 측정값 사용
                power = max(3000, self.last_power_value)  # 최소 3000W 또는 현재 측정값
            
            # 충전 시작
            self.charging = True
            self.update_status("충전 중 (수동 모드)")
            self.update_connection_status(True)
            
            # 트랜잭션 시작 이벤트 전송
            asyncio.run_coroutine_threadsafe(
                self.ocpp_client.start_charging(self.charger_id, power), 
                self.event_loop
            )
            self.transaction_started = True
            
            # 버튼 상태 업데이트
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
        except ValueError:
            messagebox.showerror("입력 오류", "유효한 숫자를 입력하세요")
        
    def stop_charging_manually(self):
        """수동 충전 중지"""
        self.stop_charging_auto()
        # 충전 중지 시 가격 정보 업데이트
        self.update_price_display()
        
    def on_closing(self):
        """창 닫기 처리"""
        # 전력 모니터링 중지
        if self.power_check_timer:
            self.after_cancel(self.power_check_timer)
            
        # 충전 중이면 중지
        if self.charging:
            if messagebox.askyesno("충전 중지", "충전이 진행 중입니다. 중지하고 창을 닫으시겠습니까?"):
                self.stop_charging_auto()
                self.destroy()
        else:
            self.destroy()
