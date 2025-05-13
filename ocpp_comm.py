"""
OCPP 충전소 시뮬레이터 - 통신 모듈
"""

import asyncio
import serial
import websockets
import json
from typing import Optional, Dict, Any

class OcppComm:
    """OCPP 통신 클래스"""
    
    def __init__(self, websocket_url, serial_port=None, baud_rate=2400, max_retries=3, retry_delay=2.0):
        self.websocket_url = websocket_url
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.websocket = None
        self.serial_conn = None
        self.receive_lock = asyncio.Lock()  # 락 추가
        self.message_queue = asyncio.Queue()  # 메시지 큐 추가
        self.is_sending = False  # 메시지 전송 중 상태 플래그
        self.last_response = None  # 마지막 응답 저장
        self.response_event = asyncio.Event()  # 응답 대기를 위한 이벤트
        
        # 재시도 관련 설정
        self.max_retries = max_retries  # 최대 재시도 횟수
        self.retry_delay = retry_delay  # 재시도 간격(초)
        
        # 메시지 처리 태스크 시작
        self.message_processor_task = None
        
        # 가격 정보 저장
        self.price_per_wh = 10  # 기본값 10원/Wh로 설정
        
        # 트랜잭션 ID 정보 저장
        self.last_transaction_id = None  # 마지막으로 수신한 트랜잭션 ID

    async def connect_websocket(self) -> bool:
        """WebSocket 연결"""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            print(f"WebSocket 연결 성공: {self.websocket_url}")
            
            # 메시지 처리 태스크 시작
            if self.message_processor_task is None or self.message_processor_task.done():
                self.message_processor_task = asyncio.create_task(self.process_message_queue())
                
            return True
        except Exception as e:
            print(f"WebSocket 연결 실패: {e}")
            return False

    def connect_serial(self) -> bool:
        """시리얼 포트 연결"""
        try:
            self.serial_conn = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            print(f"시리얼 포트 연결 성공: {self.serial_port}")
            return True
        except Exception as e:
            print(f"시리얼 포트 연결 실패: {e}")
            return False

    def close_connections(self):
        """연결 종료"""
        if self.websocket:
            asyncio.create_task(self.websocket.close())
        if self.serial_conn:
            self.serial_conn.close()
        
        # 메시지 처리 태스크 취소
        if self.message_processor_task and not self.message_processor_task.done():
            self.message_processor_task.cancel()

    async def send_message(self, message: dict) -> bool:
        """메시지 전송 (큐에 추가)"""
        if not self.websocket:
            success = await self.connect_websocket()
            if not success:
                return False
                
        # 재시도 카운터 초기화 (새 메시지)
        if "retry_count" not in message:
            message["retry_count"] = 0
                
        # 메시지를 큐에 추가
        await self.message_queue.put(message)
        return True
        
    async def process_message_queue(self):
        """메시지 큐 처리 (순차적으로 메시지 전송)"""
        try:
            while True:
                # 큐에서 메시지 가져오기
                message = await self.message_queue.get()
                
                # 메시지 전송 및 응답 대기
                success = await self._send_message_and_wait_response(message)
                
                if not success:
                    # 재시도 횟수 증가
                    if "retry_count" not in message:
                        message["retry_count"] = 0
                    message["retry_count"] += 1
                    
                    # 최대 재시도 횟수 이내인 경우 다시 큐에 추가
                    if message["retry_count"] <= self.max_retries:
                        print(f"메시지 전송 실패, {message['retry_count']}번째 재시도 예정 (최대 {self.max_retries}회)")
                        # 재시도 간격 대기
                        await asyncio.sleep(self.retry_delay)
                        await self.message_queue.put(message)
                    else:
                        print(f"메시지 전송 실패, 최대 재시도 횟수({self.max_retries}회) 초과로 포기합니다.")
                
                # 큐 작업 완료 표시
                self.message_queue.task_done()
                
        except asyncio.CancelledError:
            print("메시지 처리 태스크가 취소되었습니다.")
        except Exception as e:
            print(f"메시지 처리 중 오류 발생: {e}")

    async def _send_message_and_wait_response(self, message: dict) -> bool:
        """메시지 전송 및 응답 대기"""
        try:
            # 응답 이벤트 초기화
            self.response_event.clear()
            self.last_response = None
            
            # 메시지 전송
            json_message = json.dumps([
                message["messageTypeId"],
                message["messageId"],
                message["action"],
                message["payload"]
            ], ensure_ascii=False)
            
            retry_info = f" (재시도: {message.get('retry_count', 0)}/{self.max_retries})" if message.get('retry_count', 0) > 0 else ""
            print(f"[WebSocket sending]{retry_info} {json_message}")
            
            await self.websocket.send(json_message)
            
            # 응답 수신 태스크 시작
            receive_task = asyncio.create_task(self.receive_message())
            
            # 응답 대기 (최대 10초)
            try:
                await asyncio.wait_for(self.response_event.wait(), timeout=10.0)
                
                # "수신완료" 메시지 확인
                if self.last_response and "3" in str(self.last_response):
                    print(f"'수신완료' 응답을 받았습니다. 메시지 전송 성공.")
                    return True
                else:
                    print(f"'수신완료' 응답을 받지 못했습니다. 응답: {self.last_response}")
                    return False
            except asyncio.TimeoutError:
                print("응답 대기 시간 초과")
                return False
            finally:
                # 응답 수신 태스크가 아직 실행 중이면 취소
                if not receive_task.done():
                    receive_task.cancel()
                    
        except Exception as e:
            print(f"메시지 전송 실패: {e}")
            self.websocket = None
            return False

    async def receive_message(self):
        """메시지 수신"""
        async with self.receive_lock:  # 락 획득
            try:
                response = await self.websocket.recv()
                print(f"서버 응답: {response}")
                
                # 응답 저장 및 이벤트 설정
                self.last_response = response
                self.response_event.set()
                
                # 응답 파싱
                try:
                    response_data = json.loads(response)
                    if len(response_data) >= 3 and response_data[0] == 3:  # 응답 메시지인 경우
                        payload = response_data[2]  # 응답 페이로드
                        message_id = response_data[1]  # 메시지 ID
                        
                        # pricePermWh 값 추출
                        if "customData" in payload and "pricePermWh" in payload["customData"]:
                            self.price_per_wh = payload["customData"]["pricePermWh"]
                            print(f"가격 정보 업데이트: {self.price_per_wh}원/Wh")
                        
                        # Response에서 transactionId 추출 (메시지 ID 형식과 상관없이 추출)
                        if "customData" in payload and "transactionId" in payload["customData"]:
                            tx_id = payload["customData"]["transactionId"]
                            # tx_id가 문자열이 아니면 문자열로 변환 (예: tx-003 대신 단순 숫자인 경우)
                            if not isinstance(tx_id, str):
                                tx_id = f"tx-{int(tx_id):03d}"
                            self.last_transaction_id = tx_id
                            print(f"트랜잭션 ID 업데이트: {self.last_transaction_id}")
                except Exception as e:
                    print(f"응답 파싱 중 오류: {e}")
                
            except asyncio.CancelledError:
                print("메시지 수신 태스크가 취소되었습니다.")
            except Exception as e:
                print(f"메시지 수신 실패: {e}")
                self.websocket = None
                # 오류 발생 시에도 이벤트 설정 (대기 중인 태스크가 진행되도록)
                self.response_event.set()
