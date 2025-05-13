"""
OCPP 충전소 시뮬레이터 GUI - GUI용 OCPP 클라이언트
"""

import asyncio
import time
import random
from typing import Dict, List, Optional

from enums import EventType, TriggerReason, ConnectorStatus
from ocpp_comm import OcppComm
from ocpp_message import generate_message_id, generate_timestamp, generate_transaction_id

# 상수 정의
NUM_EVSE = 3

class GuiOcppClient:
    """GUI용 OCPP 클라이언트 클래스"""
    
    def __init__(self, app, websocket_url: str, serial_port: str = None, baud_rate: int = 2400):
        self.app = app
        # 라즈베리파이에서는 기본 시리얼 포트를 "/dev/ttyUSB0"로 설정
        if serial_port is None and self.is_raspberry_pi():
            serial_port = "/dev/ttyUSB0"
            
        self.comm = OcppComm(websocket_url, serial_port, baud_rate)
        self.power_data = [0] * NUM_EVSE
        self.prev_power_data = [0] * NUM_EVSE
        self.last_report_time = [0] * NUM_EVSE
        self.last_heartbeat_time = 0
        
        # 트랜잭션 관련 변수
        self.transaction_id_counter = 1  # 전체 시스템에서 사용하는 트랜잭션 ID 카운터
        self.transaction_ids = [None] * NUM_EVSE  # 각 충전기의 현재 트랜잭션 ID
        self.seq_num_counter = [1] * NUM_EVSE  # 시퀀스 넘버 카운터
        self.boot_notification_sent = False
        self.server_tx_id_received = False  # 서버에서 트랜잭션 ID를 받았는지 여부
        
        self.load3_mv = [0.0] * 10
        self.running = False
        self.charging_active = [False] * NUM_EVSE
        self.manual_power = [0] * NUM_EVSE  # For manual power input
        self.use_serial = serial_port is not None
        self.serial_data_valid = False
        self.cable_connected = [False] * NUM_EVSE  # 케이블 연결 상태 추적
        
        # 트랜잭션 시작 상태 추적을 위한 변수 추가
        self.transaction_started = [False] * NUM_EVSE
        
    def is_raspberry_pi(self):
        """라즈베리파이 환경인지 확인"""
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                return 'Raspberry Pi' in model
        except:
            return False

    async def send_boot_notification(self) -> bool:
        """부팅 알림 전송"""
        if self.boot_notification_sent:
            return True
        message = {
            "messageTypeId": 2,
            "messageId": generate_message_id(),
            "action": "BootNotification",
            "payload": {
                "reason": "PowerUp",
                "chargingStation": {
                    "model": "R1",
                    "vendorName": "Quarterback"
                },
                "customData": {
                    "vendorId": "Quarterback",
                    "stationId": "station-001"
                }
            }
        }
        success = await self.comm.send_message(message)
        if success:
            self.app.log("부팅 알림 전송됨")
            self.boot_notification_sent = True
        return success

    async def send_heartbeat(self) -> bool:
        """하트비트 전송"""
        current_time = time.time()
        if current_time - self.last_heartbeat_time >= 60:
            message = {
                "messageTypeId": 2,
                "messageId": generate_message_id(),
                "action": "Heartbeat",
                "payload": {}
            }
            success = await self.comm.send_message(message)
            if success:
                self.app.log("하트비트 전송됨")
                self.last_heartbeat_time = current_time
            return success
        return True

    async def send_status_notification(self, evse_id: int, status: ConnectorStatus) -> bool:
        """상태 알림 전송"""
        message = {
            "messageTypeId": 2,
            "messageId": generate_message_id(),
            "action": "StatusNotification",
            "payload": {
                "timestamp": generate_timestamp(),
                "connectorStatus": status.value,
                "evseId": evse_id,
                "connectorId": 1
            }
        }
        success = await self.comm.send_message(message)
        if success:
            self.app.log(f"EVSE {evse_id}: 상태 알림 전송됨 [{status.value}]")
            # Update charger status in GUI
            self.app.update_charger_status(evse_id, status.value)
        return success

    async def send_transaction_event_started(self, evse_id: int) -> bool:
        """트랜잭션 시작 이벤트 전송"""
        # 이미 트랜잭션이 시작된 경우 중복 전송 방지
        if self.transaction_started[evse_id - 1]:
            self.app.log(f"EVSE {evse_id}: 이미 트랜잭션이 시작되었습니다. 중복 이벤트 무시.")
            return True
        
        # 트랜잭션 ID 관리
        # 서버에서 트랜잭션 ID를 받은 적이 없고, 서버에서 받은 트랜잭션 ID가 있으면 사용
        if not self.server_tx_id_received and hasattr(self.comm, 'last_transaction_id') and self.comm.last_transaction_id:
            try:
                # 'tx-001' 형태에서 숫자 부분만 추출
                tx_id = self.comm.last_transaction_id
                if tx_id.startswith('tx-'):
                    tx_num = int(tx_id[3:])  # 'tx-001'에서 '001'을 추출하여 정수로 변환
                    # 다음 트랜잭션 ID를 위해 +1
                    self.transaction_id_counter = tx_num + 1
                    self.app.log(f"서버 응답에서 트랜잭션 ID({tx_id})를 기반으로 다음 ID 설정: tx-{self.transaction_id_counter:03d}")
                    self.server_tx_id_received = True  # 서버에서 ID를 받았음을 표시
            except (ValueError, AttributeError) as e:
                self.app.log(f"트랜잭션 ID 파싱 오류: {e}. 기본 카운터 사용.")
        
        # 현재 충전기에 트랜잭션 ID 할당
        current_tx_id = self.transaction_id_counter
        self.transaction_ids[evse_id - 1] = current_tx_id
        self.app.log(f"충전기 {evse_id}에 트랜잭션 ID tx-{current_tx_id:03d} 할당")
        
        # 다음 트랜잭션을 위해 카운터 증가 (다음 충전기가 사용할 ID 준비)
        self.transaction_id_counter += 1
        
        # TransactionEvent 메시지 생성
        message = {
            "messageTypeId": 2,
            "messageId": generate_message_id(),
            "action": "TransactionEvent",
            "payload": {
                "eventType": EventType.STARTED.value,
                "timestamp": generate_timestamp(),
                "triggerReason": TriggerReason.CABLE_PLUGGED_IN.value,
                "seqNo": self.seq_num_counter[evse_id - 1],
                "transactionInfo": {
                    "transactionId": generate_transaction_id(current_tx_id)
                },
                "evse": {
                    "id": evse_id
                },
                "idToken": {
                    "idToken": "token001",
                    "type": "Central"
                },
                "customData": {
                    "vendorId": "Quarterback",
                    "vehicleInfo": {
                        "vehicleNo": "38-473",
                        "model": "GV-60",
                        "batteryCapacityKWh": 72000,
                        "requestedEnergyKWh": 30000
                    }
                }
            }
        }
        
        self.seq_num_counter[evse_id - 1] += 1
        success = await self.comm.send_message(message)
        if success:
            self.app.log(f"EVSE {evse_id}: 충전 시작 이벤트 전송됨 (트랜잭션 ID: tx-{current_tx_id:03d})")
            self.transaction_started[evse_id - 1] = True
        return success

    async def send_transaction_event_updated(self, evse_id: int, power_value: int) -> bool:
        """트랜잭션 업데이트 이벤트 전송"""
        # 트랜잭션이 시작되지 않은 경우 업데이트 이벤트 무시
        if not self.transaction_started[evse_id - 1] or self.transaction_ids[evse_id - 1] is None:
            return False
            
        message = {
            "messageTypeId": 2,
            "messageId": generate_message_id(),
            "action": "TransactionEvent",
            "payload": {
                "eventType": EventType.UPDATED.value,
                "timestamp": generate_timestamp(),
                "triggerReason": TriggerReason.METER_VALUE_PERIODIC.value,
                "seqNo": self.seq_num_counter[evse_id - 1],
                "transactionInfo": {
                    "transactionId": generate_transaction_id(self.transaction_ids[evse_id - 1])
                },
                "evse": {
                    "id": evse_id
                },
                "idToken": {
                    "idToken": "token001",
                    "type": "Central"
                },
                "meterValue": [
                    {
                        "timestamp": generate_timestamp(),
                        "sampledValue": [
                            {
                                "value": power_value
                            }
                        ]
                    }
                ]
            }
        }
        self.seq_num_counter[evse_id - 1] += 1
        success = await self.comm.send_message(message)
        if success:
            self.app.log(f"EVSE {evse_id}: 전력 사용량 전송됨 [{power_value}W] (트랜잭션 ID: tx-{self.transaction_ids[evse_id - 1]:03d})")
        return success

    async def send_transaction_event_ended(self, evse_id: int, power_value: int) -> bool:
        """트랜잭션 종료 이벤트 전송"""
        # 트랜잭션이 시작되지 않은 경우 종료 이벤트 무시
        if not self.transaction_started[evse_id - 1] or self.transaction_ids[evse_id - 1] is None:
            return False
            
        message = {
            "messageTypeId": 2,
            "messageId": generate_message_id(),
            "action": "TransactionEvent",
            "payload": {
                "eventType": EventType.ENDED.value,
                "timestamp": generate_timestamp(),
                "triggerReason": TriggerReason.EV_DISCONNECTED.value,
                "seqNo": self.seq_num_counter[evse_id - 1],
                "transactionInfo": {
                    "transactionId": generate_transaction_id(self.transaction_ids[evse_id - 1])
                },
                "evse": {
                    "id": evse_id
                },
                "idToken": {
                    "idToken": "token001",
                    "type": "Central"
                },
                "meterValue": [
                    {
                        "timestamp": generate_timestamp(),
                        "sampledValue": [
                            {
                                "value": power_value
                            }
                        ]
                    }
                ]
            }
        }
        self.seq_num_counter[evse_id - 1] += 1
        success = await self.comm.send_message(message)
        if success:
            self.app.log(f"EVSE {evse_id}: 충전 종료 이벤트 전송됨, 마지막 보고된 전력 [{power_value}W] (트랜잭션 ID: tx-{self.transaction_ids[evse_id - 1]:03d})")
            self.transaction_started[evse_id - 1] = False  # 트랜잭션 종료 상태로 변경
            self.transaction_ids[evse_id - 1] = None  # 트랜잭션 ID 초기화
        return success

    async def send_meter_values(self, evse_id: int, power_value: int) -> bool:
        """미터 값 전송"""
        message = {
            "messageTypeId": 2,
            "messageId": generate_message_id(),
            "action": "MeterValues",
            "payload": {
                "meterValue": [
                    {
                        "timestamp": generate_timestamp(),
                        "sampledValue": [
                            {
                                "value": power_value,
                                "measurand": "Power.Active.Import"
                            }
                        ]
                    }
                ]
            }
        }
        success = await self.comm.send_message(message)
        if success:
            self.app.log(f"EVSE {evse_id}: 미터 값 전송됨 [{power_value}W]")
        return success

    def get_load3_data(self, number_of_load: int) -> bool:
        """로드 데이터 가져오기"""
        if not self.use_serial or not self.comm.serial_conn:
            # If not using serial, use manual power values
            for i in range(NUM_EVSE):
                if self.charging_active[i]:
                    self.load3_mv[i*2] = 220.0  # Voltage
                    self.load3_mv[i*2+1] = self.manual_power[i] / 220.0  # Current
                else:
                    self.load3_mv[i*2] = 0.0
                    self.load3_mv[i*2+1] = 0.0
            return True
            
        try:
            self.comm.serial_conn.reset_input_buffer()
            start_time = time.time()
            timeout = 1.0
            while time.time() - start_time < timeout:
                if self.comm.serial_conn.in_waiting > 0:
                    char = self.comm.serial_conn.read(1).decode('ascii', errors='ignore')
                    if char == '!':
                        break
            if time.time() - start_time >= timeout:
                self.app.log("시리얼 데이터 시작 문자를 찾지 못함")
                self.serial_data_valid = False
                return False
            data = ""
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.comm.serial_conn.in_waiting > 0:
                    char = self.comm.serial_conn.read(1).decode('ascii', errors='ignore')
                    if char == '@':
                        break
                    elif char == '!':
                        data = ""
                    elif char in "0123456789. ":
                        data += char
            if not data:
                self.app.log("유효한 시리얼 데이터를 읽지 못함")
                self.serial_data_valid = False
                return False
            values = data.strip().split()
            for i in range(min(len(values), 10)):
                try:
                    self.load3_mv[i] = float(values[i])
                except ValueError:
                    self.app.log(f"잘못된 데이터 형식: {values[i]}")
            self.serial_data_valid = True
            
            # 케이블 연결 상태 감지 (전압이 있으면 케이블이 연결된 것으로 간주)
            for i in range(NUM_EVSE):
                if i*2 < len(self.load3_mv):
                    voltage = self.load3_mv[i*2]
                    # 전압이 임계값(예: 50V) 이상이면 케이블이 연결된 것으로 간주
                    if voltage > 50.0:
                        if not self.cable_connected[i]:
                            self.cable_connected[i] = True
                            self.app.log(f"충전기 {i+1}: 케이블 연결 감지됨")
                            # 케이블이 연결되었지만 충전이 활성화되지 않은 경우 전력 차단 명령 전송
                            if not self.charging_active[i]:
                                self.send_power_control_command(i+1, False)
                    else:
                        if self.cable_connected[i]:
                            self.cable_connected[i] = False
                            self.app.log(f"충전기 {i+1}: 케이블 연결 해제됨")
            
            return True
        except Exception as e:
            self.app.log(f"시리얼 데이터 읽기 오류: {e}")
            self.serial_data_valid = False
            return False

    def send_power_control_command(self, port_number: int, enable: bool) -> bool:
        """특정 포트의 전력 공급을 제어하는 명령 전송"""
        if not self.use_serial or not self.comm.serial_conn:
            self.app.log(f"시리얼 연결이 없어 전력 제어 명령을 전송할 수 없습니다.")
            return False
            
        try:
            # 명령 형식: "P,포트번호,상태\n"
            # 상태: 1=켜기, 0=끄기
            command = f"P,{port_number},{1 if enable else 0}\n"
            self.comm.serial_conn.write(command.encode('ascii'))
            self.app.log(f"충전기 {port_number}: 전력 {'공급' if enable else '차단'} 명령 전송됨")
            return True
        except Exception as e:
            self.app.log(f"전력 제어 명령 전송 오류: {e}")
            return False

    def measure_load_sensor(self, number_of_load: int) -> List[int]:
        """로드 센서 측정"""
        load_w = [0] * number_of_load
        for i in range(number_of_load):
            if i*2+1 < len(self.load3_mv):
                # 충전이 활성화된 경우에만 전력 계산
                if self.charging_active[i]:
                    load_w[i] = int(self.load3_mv[i*2] * self.load3_mv[i*2+1])
                    if load_w[i] < 100:
                        load_w[i] = 0
                else:
                    load_w[i] = 0
        return load_w

    def print_load_w(self, number_of_load: int, load_w: List[int]):
        """로드 전력 출력"""
        load_str = "W: " + " ".join([f"{w}" for w in load_w])
        self.app.log(load_str)

    def update_power_data(self, evse_id: int, power_value: int):
        """전력 데이터 업데이트"""
        if 1 <= evse_id <= NUM_EVSE:
            self.power_data[evse_id - 1] = power_value
            # Update power display in GUI
            self.app.update_power_display(evse_id, power_value)

    async def check_charging_start(self):
        """충전 시작 확인"""
        for i in range(NUM_EVSE):
            if self.prev_power_data[i] == 0 and self.power_data[i] > 0:
                evse_id = i + 1
                # 상태 알림만 보내고, 트랜잭션 이벤트는 start_charging에서만 보냄
                if not self.transaction_started[i]:
                    await self.send_status_notification(evse_id, ConnectorStatus.OCCUPIED)
                    # 트랜잭션 이벤트는 start_charging에서 이미 보냈으므로 여기서는 보내지 않음
                    # await self.send_transaction_event_started(evse_id)

    async def report_power_usage(self):
        """전력 사용량 보고"""
        current_time = time.time()
        for i in range(NUM_EVSE):
            if self.power_data[i] <= 0:
                continue
            if current_time - self.last_report_time[i] >= 1:
                evse_id = i + 1
                await self.send_transaction_event_updated(evse_id, self.power_data[i])
                await self.send_meter_values(evse_id, self.power_data[i])
                self.last_report_time[i] = current_time

    async def check_charging_end(self):
        """충전 종료 확인"""
        for i in range(NUM_EVSE):
            if self.prev_power_data[i] > 0 and self.power_data[i] == 0:
                evse_id = i + 1
                await self.send_transaction_event_ended(evse_id, self.prev_power_data[i])
                await self.send_status_notification(evse_id, ConnectorStatus.AVAILABLE)
                self.last_report_time[i] = 0
                self.charging_active[i] = False
            self.prev_power_data[i] = self.power_data[i]

    async def start_charging(self, evse_id: int, power_value: int):
        """충전 시작"""
        if 1 <= evse_id <= NUM_EVSE:
            port_idx = evse_id - 1
            self.manual_power[port_idx] = power_value
            self.charging_active[port_idx] = True
            self.app.log(f"충전기 {evse_id}의 충전을 시작합니다. 전력: {power_value}W")
            
            # 시리얼 연결이 있는 경우 전력 공급 명령 전송
            if self.use_serial:
                self.send_power_control_command(evse_id, True)
            
            # Update status to Occupied
            await self.send_status_notification(evse_id, ConnectorStatus.OCCUPIED)
            
            # 트랜잭션 시작 이벤트 전송 (여기서만 전송)
            await self.send_transaction_event_started(evse_id)
            
            return True
        return False

    async def stop_charging(self, evse_id: int):
        """충전 중지"""
        if 1 <= evse_id <= NUM_EVSE:
            port_idx = evse_id - 1
            final_power = self.manual_power[port_idx]
            self.manual_power[port_idx] = 0
            self.charging_active[port_idx] = False
            self.app.log(f"충전기 {evse_id}의 충전을 중지합니다.")
            
            # 시리얼 연결이 있는 경우 전력 차단 명령 전송
            if self.use_serial:
                self.send_power_control_command(evse_id, False)
            
            # Update status to Available
            await self.send_transaction_event_ended(evse_id, final_power)
            await self.send_status_notification(evse_id, ConnectorStatus.AVAILABLE)
            
            return True
        return False

    async def run_loop(self):
        """메인 루프 실행"""
        self.running = True
        self.app.log("OCPP 클라이언트 시작")
        
        websocket_connected = False
        if self.comm.websocket_url:
            websocket_connected = await self.comm.connect_websocket()
            
        serial_connected = True
        if self.use_serial:
            serial_connected = self.comm.connect_serial()
            if not serial_connected:
                self.app.log("시리얼 포트 연결 실패. 수동 모드로 전환합니다.")
                self.use_serial = False
        
        current_time = time.time()
        self.last_heartbeat_time = current_time
        for i in range(NUM_EVSE):
            self.last_report_time[i] = current_time
            self.power_data[i] = 0
            self.prev_power_data[i] = 0
            self.transaction_started[i] = False  # 트랜잭션 시작 상태 초기화
            
        if websocket_connected:
            await self.send_boot_notification()
            for i in range(NUM_EVSE):
                await self.send_status_notification(i + 1, ConnectorStatus.AVAILABLE)
                
        number_of_load3 = NUM_EVSE
        self.app.log("메인 루프 시작...")
        
        # 시리얼 연결 실패 시 임시 데이터 생성
        if self.use_serial and not serial_connected:
            self.app.log("시리얼 연결 실패. 임시 데이터를 사용합니다.")
            self.use_serial = False
            
        try:
            while self.running:
                if self.comm.websocket_url and not self.comm.websocket and websocket_connected:
                    websocket_connected = await self.comm.connect_websocket()
                    if websocket_connected:
                        self.boot_notification_sent = False
                        await self.send_boot_notification()
                        for i in range(NUM_EVSE):
                            await self.send_status_notification(i + 1, ConnectorStatus.AVAILABLE)
                    else:
                        await asyncio.sleep(0.1)
                        continue
                        
                read_success = self.get_load3_data(number_of_load3)
                
                # 시리얼 데이터 읽기 실패 시 임시 데이터 생성
                if not read_success and self.use_serial:
                    self.app.log("시리얼 데이터 읽기 실패. 임시 데이터를 사용합니다.")
                    # Generate temporary data for active chargers
                    for i in range(NUM_EVSE):
                        if self.charging_active[i]:
                            base_power = self.manual_power[i] if self.manual_power[i] > 0 else 3000
                            variation = random.uniform(-200, 200)
                            self.load3_mv[i*2] = 220.0  # Voltage
                            self.load3_mv[i*2+1] = (base_power + variation) / 220.0  # Current
                        else:
                            self.load3_mv[i*2] = 0.0
                            self.load3_mv[i*2+1] = 0.0
                    read_success = True
                
                if read_success:
                    load3_w = self.measure_load_sensor(number_of_load3)
                    self.print_load_w(number_of_load3, load3_w)
                    for i in range(min(number_of_load3, NUM_EVSE)):
                        self.update_power_data(i + 1, load3_w[i])
                    await self.check_charging_start()
                    await self.check_charging_end()
                    if websocket_connected:
                        await self.report_power_usage()
                        await self.send_heartbeat()
                else:
                    self.app.log("데이터 읽기 오류")
                    
                await asyncio.sleep(0.1)
        except Exception as e:
            self.app.log(f"오류 발생: {e}")
        finally:
            self.comm.close_connections()
            self.app.log("OCPP 클라이언트 종료")
            self.running = False

    def stop(self):
        """클라이언트 중지"""
        self.running = False
