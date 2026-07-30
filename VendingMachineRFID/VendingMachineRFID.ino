#include <SPI.h>
#include <MFRC522.h>
// RFID 핀 설정 (CNC 쉴드 검은 핀 기준)
#define SS_PIN 10  // Y+
#define RST_PIN 9  // X+
MFRC522 rfid(SS_PIN, RST_PIN);
// 모터 핀 설정 (배선하신 X/Y 위치가 반대라서 코드에서 뒤집어 주었습니다!)
#define STEP_Y 2 // 수직 모터 (층 이동)
#define DIR_Y 5
#define STEP_X 3 // 수평 모터 (푸셔)
#define DIR_X 6
#define EN_PIN 8 // 모터 Enable (LOW일 때 활성화)
// 층별 수직 이동 스텝 수 설정 (정회전으로 움직이도록 양수로 변경)
// 현재 1층은 2000, 2층은 4000으로 설정했습니다. 기계 크기에 맞춰 숫자를 조정하세요!
long floorSteps[4] = {2000, 4000, 6000, 8000}; 
long currentVerticalPos = 0;
void setup() {
  Serial.begin(9600);
  
  // RFID 초기화
  SPI.begin();
  rfid.PCD_Init();
  
  // 모터 핀 초기화
  pinMode(STEP_Y, OUTPUT);
  pinMode(DIR_Y, OUTPUT);
  pinMode(STEP_X, OUTPUT);
  pinMode(DIR_X, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);
  
  Serial.println("READY");
}
void loop() {
  // 1. RFID 카드 감지 (사용자가 성공했던 코드 100% 그대로 적용)
  if (rfid.PICC_IsNewCardPresent()) {
    Serial.println("TOPTEC 사원 부기공 확인 완료");
    
    // UI 잠금 해제를 위한 신호도 몰래 같이 보냅니다.
    Serial.println("TAG:PASS");
    
    delay(1000); // 1초에 한 번씩만 출력되도록 딜레이
  }
  
  // 2. 웹 UI 명령 수신 (배출 명령)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'A') processDispense(0); // 1층
    else if (cmd == 'B') processDispense(1); // 2층
    else if (cmd == 'C') processDispense(2); // 3층
    else if (cmd == 'D') processDispense(3); // 4층
  }
}
// 수직 이동 함수
void moveVertical(long targetSteps) {
  long diff = targetSteps - currentVerticalPos;
  if (diff == 0) return;
  
  digitalWrite(DIR_Y, (diff > 0) ? HIGH : LOW);
  long stepsToMove = abs(diff);
  
  for (long i = 0; i < stepsToMove; i++) {
    digitalWrite(STEP_Y, HIGH);
    delayMicroseconds(800);
    digitalWrite(STEP_Y, LOW);
    delayMicroseconds(800);
  }
  currentVerticalPos = targetSteps;
}
// 엔드밀 밀어내기 함수
void pushItem() {
  digitalWrite(DIR_X, LOW); // 정회전으로 밀어내기 (HIGH->LOW로 수정)
  for (int i = 0; i < 1000; i++) { // 구동 거리를 반으로 줄임 (2000 -> 1000)
    digitalWrite(STEP_X, HIGH);
    delayMicroseconds(2500); // 수평 모터 힘(토크)을 높이기 위해 1500 -> 2500으로 속도 낮춤
    digitalWrite(STEP_X, LOW);
    delayMicroseconds(2500);
  }
}
// 푸셔 복귀 함수
void returnPusher() {
  digitalWrite(DIR_X, HIGH); // 역회전으로 복귀 (LOW->HIGH로 수정)
  for (int i = 0; i < 1000; i++) { // 구동 거리를 반으로 줄임 (2000 -> 1000)
    digitalWrite(STEP_X, HIGH);
    delayMicroseconds(2500); // 수평 모터 힘(토크)을 높이기 위해 속도 낮춤
    digitalWrite(STEP_X, LOW);
    delayMicroseconds(2500);
  }
}
// 전체 배출 과정 함수
void processDispense(int floorIndex) {
  Serial.println("STATUS:MOVING");
  moveVertical(floorSteps[floorIndex]);
  Serial.println("STATUS:ARRIVED");
  delay(500);
  
  Serial.println("STATUS:PUSHING");
  pushItem();
  delay(500);
  
  Serial.println("STATUS:RETURNING");
  returnPusher();
  delay(500);
  
  // 원래 자리(1층=0)로 복귀
  moveVertical(0);
  
  Serial.println("STATUS:DONE");
}
