# 🏆 AI 스마트 공구 자판기 (AI Smart Endmill Vending Machine)

**제4회 NAVER OGQ마켓 AI Competition - AI × 산업 혁신 트랙 출품작**
**Team:** 툴토리얼 (Tooltorial)

## 1. 🚨 문제 정의 (Problem Definition)
제조 산업 현장의 핵심인 공작기계 공정에서 정밀함을 좌우하는 '엔드밀' 관리는 여전히 아날로그 방식에 머물러 있습니다.
* **안전 및 보관 문제:** 날카롭고 값비싼 공구들이 분류 없이 일반 공구함에 수북이 겹쳐 보관되어 작업자가 손을 다치거나, 공구끼리 부딪혀 사용 전부터 날이 손상됩니다.
* **주관적 육안 검사의 한계:** 공구의 파손 상태를 작업자의 주관적인 판단에 의존하므로 가공 품질이 일정하지 않으며, 아직 쓸 수 있는 공구를 조기 폐기하여 막대한 경제적 손실을 초래합니다.

## 2. 💡 핵심 솔루션 (Core Solution)
YOLOv26 비전 AI와 아두이노 하드웨어 제어를 결합하여, **불량 공구를 객관적으로 걸러내고 안전하게 자동 배출하는 스마트 자판기 시스템**입니다.
* **AI 상태 판별:** 웹캠을 통해 공구의 미세 파손 상태를 5단계 클래스로 실시간 객체 탐지합니다.
* **스마트 자동 배출:** Web Serial API를 활용해 웹 브라우저에서 아두이노를 직접 제어하며, RFID 인증을 거쳐 지정된 층의 공구를 스텝 모터로 밀어냅니다.

## 3. 🏗️ 시스템 아키텍처 및 동작 흐름 (Architecture)
본 시스템은 Web(소프트웨어)과 Arduino(하드웨어)가 실시간 양방향 통신하는 구조로 설계되었습니다.

1. **인증:** 작업자가 RFID 카드 태그 → 아두이노에서 웹 UI로 `TAG:PASS` 시리얼 전송 → 웹 UI 잠금 해제
2. **제어:** 사용자가 웹 UI에서 층 선택 → Web Serial API를 통해 아두이노로 명령(A/B/C/D) 전송
3. **구동:** 아두이노가 수직 모터(층 이동)와 수평 모터(푸셔 배출)를 제어하여 공구 배출
4. **AI 검사:** Flask 서버가 웹캠 영상을 수신하여 실시간 YOLOv26 추론 후 검사 결과를 웹 UI로 스트리밍 (MJPEG)

## 4. 🛠️ 기술 스택 (Tech Stack)
* **AI Model:** `YOLOv26n` (커스텀 데이터셋 전이 학습), `OpenCV` (영상 프레임 제어)
* **Backend:** `Python`, `Flask` (YOLO 추론 및 실시간 영상 스트리밍 API 서버)
* **Frontend:** `HTML`, `CSS`, `JavaScript`, `Web Serial API` (하드웨어 통신)
* **Hardware:** `Arduino Uno`, `CNC Shield v3`, `NEMA 17 스텝 모터`(2ea), `MFRC522 RFID`
* **Data & Environment:** `Roboflow`, `NVIDIA RTX 4060 (CUDA)`

## 5. 🧠 AI 모델 학습 상세 (AI Usage & Training)
단순 사전학습 모델이 아닌, 현장 상황에 맞춘 자체 커스텀 데이터셋을 구축하여 파인튜닝을 진행했습니다

* **학습 베이스 모델:** YOLOv26n (경량화 모델로 하드웨어 실시간 피드백에 최적화)
* **데이터셋 (Roboflow):** 총 1,062장 (학습 746장, 검증 211장, 테스트 105장)
* **클래스 정의 (5종):** 양품(`good`), 미세 손상(`little`), 파손(`destroyed`), 이중 파손(`double break`), 기타(`qwert`)
* **학습 결과:** 100 Epoch 완주, **mAP50 기준 99.50%**의 높은 정확도 달성 (상세 그래프 및 혼동 행렬은 저장소의 `runs` 폴더 내 결과 파일 참조

## 6. ⚙️ 하드웨어 트러블슈팅 (Hardware Details)
* **모터 탈조 및 토크 문제 해결:** 초기 1A 파워서플라이 환경에서 수평 모터가 헛도는 현상을 파악하고, 전압/전류를 **12V / 3~5A**로 상향 및 펄스 딜레이 조정을 통해 토크를 안정적으로 확보했습니다
* **배선 매핑 최적화:** CNC Shield의 X/Y축 물리적 배선 반전 이슈를 소프트웨어적 핀 교차 매핑(STEP_Y=핀2, STEP_X=핀3)으로 해결하여 구동 안정성을 높였습니다

## 7. 🚀 실행 방법 (How to Run)
1. 하드웨어 전원을 켭니다. (파워서플라이 12V 3~5A 설정)
2. Arduino IDE를 이용해 `VendingMachineRFID/VendingMachineRFID.ino`를 업로드합니다
3. 웹캠을 연결하고 파이썬 가상환경에서 서버를 구동합니다.

## 8. ⚖️ 외부 사용 내역 및 오픈소스 라이선스
본 프로젝트는 대회 규정에 따라 아래의 외부 자원 및 오픈소스 생태계를 활용하여 개발되었음을 명시합니다.

* **사용한 AI 모델 (비전 탐지 및 코드 생성)**:
  * Ultralytics YOLOv26: 엔드밀 파손 상태 실시간 객체 탐지 모델 (AGPL-3.0 License)
  * Claude & Gemini: 아두이노 하드웨어 제어 코드 및 프론트엔드 UI/웹 로직 작성 보조
* **오픈소스 패키지 및 라이브러리**:
  * OpenCV: 실시간 웹캠 스트리밍 제어 (Apache 2.0 License)
  * Flask: 파이썬 기반 웹 API 서버 구축 (BSD-3-Clause License)
  * Antigravity: UI 및 프론트엔드 요소 적용
* **외부 서비스**: 
  * Roboflow: 데이터셋 호스팅 및 라벨링 (CC BY 4.0 License)
* **기타 에셋**: 
  * Google Fonts: Inter 폰트 적용 (OFL)
* **외부 자문 내역**: 본교 선생님들께(기계과,정보과) 제어와 프로그래밍에 관한 자문을 구함
   ```bash
   call yolo_env\Scripts\activate.bat
   python app.py
