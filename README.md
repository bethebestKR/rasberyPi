# ⚡ 전기차 충전소 관리 시스템 — 라즈베리파이 / 아두이노 모듈

> **캡스톤디자인 (2025 봄학기) — 팀 QuarterBack**
>
> OCPP 2.0.1 프로토콜 기반의 전기차 충전소 IoT 클라이언트입니다.  
> 라즈베리파이가 충전소 단말(EVSE) 역할을 수행하며, 아두이노를 통해 실제 충전기 플러그 탈착을 감지하고  
> WebSocket으로 백엔드 OCPP 서버와 실시간 통신합니다.

<br/>

## 📌 담당 역할

본 레포지토리는 팀 프로젝트에서 **라즈베리파이 & 아두이노 파트**를 담당한 코드입니다.

- 아두이노로 충전기 케이블 탈착 신호를 감지하여 시리얼 통신으로 라즈베리파이에 전송
- 라즈베리파이에서 OCPP 2.0.1 메시지를 생성하여 백엔드 서버로 전송
- 충전 시작 → 전력 측정 → 충전 종료 전 과정을 시나리오로 구현
- tkinter 기반 GUI 대시보드로 3개 충전기(EVSE) 상태를 실시간 시각화

<br/>

## 🏗️ 시스템 구성도

```
[ 아두이노 ]
  └─ 충전기 케이블 탈착 감지 (전류/전압 측정)
  └─ 시리얼 통신 (Serial, Baud Rate: 2400) ──→

[ 라즈베리파이 4B ]                              [ 백엔드 서버 ]
  └─ Python GUI 앱 실행                           └─ Java Spring Boot
  └─ OCPP 2.0.1 메시지 생성/파싱      WebSocket   └─ OCPP WebSocket Handler
  └─ WebSocket 클라이언트       ←────────────────→ └─ MySQL / MongoDB / Redis
  └─ 충전 트랜잭션 관리                            └─ REST API
  └─ 실시간 전력 모니터링 GUI                      └─ 관리자 웹 대시보드 (React)
```

<br/>

## ✨ 주요 기능

| 기능 | 설명 |
|---|---|
| 🔌 **충전기 탈착 감지** | 아두이노에서 케이블 연결/분리 신호를 시리얼로 수신 |
| 📡 **OCPP 통신** | BootNotification, Authorize, TransactionEvent, MeterValue 등 메시지 송수신 |
| 🔑 **사용자 인증** | idToken 기반 `Authorize` 요청으로 충전 인증 처리 |
| ⚡ **실시간 전력 모니터링** | 시리얼 포트로 전력값(W) 수신 및 그래프 시각화 |
| 💰 **충전 요금 계산** | 서버로부터 수신한 단가(원/Wh) 기반 실시간 요금 계산 |
| 🔄 **자동 재시도** | 메시지 전송 실패 시 최대 3회 자동 재시도 (큐 기반 순차 처리) |
| 🖥️ **GUI 대시보드** | tkinter 기반 3개 EVSE 동시 모니터링 + 로그 뷰어 |
| 🔧 **수동 모드** | 시리얼 포트 없이 전력값을 직접 입력하는 테스트 모드 지원 |

<br/>

## 🛠️ 기술 스택

### 라즈베리파이 (이 레포)

| 항목 | 내용 |
|---|---|
| **언어** | Python 3.x |
| **GUI** | tkinter, ttk |
| **WebSocket** | `websockets >= 10.0` |
| **시리얼 통신** | `pyserial >= 3.5` |
| **비동기 처리** | `asyncio`, `threading` |
| **프로토콜** | OCPP 2.0.1 |
| **하드웨어** | Raspberry Pi 4B + Arduino |

### 백엔드 서버 (연동 시스템)

| 항목 | 내용 |
|---|---|
| **언어 / 프레임워크** | Java 17, Spring Boot 3.3.1 |
| **통신** | WebSocket (OCPP 핸들러), REST API |
| **인증** | Spring Security + JWT |
| **DB** | MySQL, MongoDB, Redis |
| **문서화** | Swagger (springdoc-openapi 2.0.2) |
| **빌드** | Gradle |

<br/>

## 📁 파일 구조

```
rasberyPi/
├── main.py                  # 진입점 — GUI 앱 실행
├── gui_app.py               # tkinter 메인 애플리케이션 (3 EVSE 관리)
├── gui_client.py            # OCPP 클라이언트 — 메시지 생성 및 충전 시나리오
├── ocpp_comm.py             # WebSocket 통신 모듈 (메시지 큐, 재시도 로직)
├── ocpp_message.py          # 메시지 ID / 타임스탬프 / 트랜잭션 ID 생성 유틸
├── charger_windows.py       # 충전기별 팝업 창 (로그인, 충전 제어)
├── visual_dashboard.py      # 전력 미터, 상태 시각화 위젯
├── enums.py                 # EventType, TriggerReason, ConnectorStatus 열거형
├── utils.py                 # 설정 저장/불러오기, 전력값 포맷팅 유틸
├── requirements.txt         # 의존성 목록
└── logs/                    # 실행 로그 저장 디렉토리
```

<br/>

## ⚙️ OCPP 메시지 흐름

충전 한 사이클의 시나리오입니다.

```
라즈베리파이                              백엔드 서버
     │                                        │
     │── BootNotification ──────────────────→ │  (부팅 시 1회)
     │← BootNotification Response ─────────── │
     │                                        │
     │── Authorize (idToken) ───────────────→ │  (사용자 인증)
     │← Authorize Response ─────────────────── │
     │                                        │
     │  [아두이노: 케이블 연결 감지]            │
     │── TransactionEvent (Started) ─────────→ │  (충전 시작)
     │← TransactionEvent Response ──────────── │  (transactionId 수신)
     │                                        │
     │── MeterValue (전력 데이터 주기 전송) ──→ │  (충전 중)
     │                                        │
     │  [아두이노: 케이블 분리 감지]            │
     │── TransactionEvent (Ended) ────────────→ │  (충전 종료)
     │← TransactionEvent Response ──────────── │
```

<br/>

## 🚀 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 실행

```bash
python main.py
```

### 3. GUI 설정

| 항목 | 기본값 | 설명 |
|---|---|---|
| WebSocket URL | `ws://localhost:8080/ocpp` | 백엔드 서버 주소 |
| 시리얼 포트 | `/dev/ttyUSB0` (라즈베리파이 자동) | 아두이노 연결 포트 |
| Baud Rate | `2400` | 시리얼 통신 속도 |
| 수동 모드 | 체크 해제 | 시리얼 없이 수동 전력 입력 |

> 라즈베리파이 환경에서는 시리얼 포트가 `/dev/ttyUSB0`으로 자동 설정됩니다.  
> Windows 테스트 환경에서는 `COM3` 등으로 직접 입력하거나 수동 모드를 사용하세요.

<br/>

## 👥 팀원

| 이름 | 역할 |
|---|---|
| 마영창 | 라즈베리파이 / 아두이노 **(본 레포)** |
| 이동호 | 백엔드 (Spring Boot, OCPP 서버) |
| 김태원 | 팀원 |
| 윤덕규 | 팀원 |

<br/>

## 🔗 전체 프로젝트 확인

본 레포는 전체 시스템의 라즈베리파이 파트입니다.  
프로젝트 전체 구성 및 다른 모듈은 아래 GitHub 조직 페이지에서 확인하세요.

> 👉 **[https://github.com/Capstone-QuarterBack](https://github.com/Capstone-QuarterBack)**

| 레포지토리 | 설명 |
|---|---|
| [rasberyPi](https://github.com/Capstone-QuarterBack/rasberyPi) | 🔴 라즈베리파이 / 아두이노 클라이언트 **(현재 레포)** |
| [backend](https://github.com/Capstone-QuarterBack/backend) | Spring Boot 기반 OCPP 서버 |
| [frontend](https://github.com/Capstone-QuarterBack/frontend) | 관리자 웹 대시보드 (React/TypeScript) |
| [front](https://github.com/Capstone-QuarterBack/front) | 프론트엔드 (TypeScript) |

<br/>

---

> 세종대학교 컴퓨터공학과 | 2025 캡스톤디자인 | 팀 QuarterBack (컴1-13)
