#include <SPI.h>
#include <MFRC522.h>
#include <Stepper.h>

// RFID 핀 설정 (CNC 쉴드 간섭 없는 핀)
#define SS_PIN 10  // Y+
#define RST_PIN 9  // X+
MFRC522 rfid(SS_PIN, RST_PIN);

// 모터 핀 설정 (배선하신 X/Y 위치)
#define STEP_Y 2 // 수직 모터 (엘리베이터)
#define DIR_Y 5
#define STEP_X 3 // 수평 모터 (엔드밀 푸셔)
#define DIR_X 6
#define EN_PIN 8 // 모터 Enable (LOW일 때 활성화)

// 층별 수직 이동 스텝 수 설정
long floorSteps[4] = {3000, 3600, 4200, 5400}; 
long currentVerticalPos = 0;

// ===== L298N 선반 바이트 (4층) 설정 =====
int latheStepsPerStage = 1500; 
int lathePressCount = 0;
int currentLatheTarget = 0;
Stepper latheStepper(200, A0, A1, A2, A3);

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
  digitalWrite(EN_PIN, LOW); // A4988 활성화
  
  // L298N 제어 핀 초기화
  pinMode(A0, OUTPUT);
  pinMode(A1, OUTPUT);
  pinMode(A2, OUTPUT);
  pinMode(A3, OUTPUT);
  latheStepper.setSpeed(60);
  
  Serial.println("READY");
}

void loop() {
  // 1. RFID 카드 감지
  if (rfid.PICC_IsNewCardPresent()) {
    Serial.println("TOPTEC 사원증 확인 완료");
    Serial.println("TAG:PASS");
    delay(1000);
  }
  
  // 2. 웹 UI 명령 수신 (배출 명령)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'A') processDispense(0); // 1층 - 엔드밀
    else if (cmd == 'B') processDispense(1); // 2층 - 엔드밀
    else if (cmd == 'C') processDispense(2); // 3층 - 엔드밀
    else if (cmd == 'D') processDispense(3); // 4층 - 선반 바이트
  }
}

// 수직 이동 함수 (엘리베이터)
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

// ===== 엔드밀 푸셔 (1~3층) =====
void pushItem() {
  digitalWrite(DIR_X, HIGH);
  for (int i = 0; i < 800; i++) { 
    digitalWrite(STEP_X, HIGH);
    delayMicroseconds(2500); 
    digitalWrite(STEP_X, LOW);
    delayMicroseconds(2500);
  }
}

void returnPusher() {
  digitalWrite(DIR_X, LOW);
  for (int i = 0; i < 800; i++) {
    digitalWrite(STEP_X, HIGH);
    delayMicroseconds(2500);
    digitalWrite(STEP_X, LOW);
    delayMicroseconds(2500);
  }
}

// ===== 선반 바이트 푸셔 (4층 - L298N) =====
void pushLathe() {
  lathePressCount++;
  if (lathePressCount > 3) {
    lathePressCount = 1;
  }
  
  currentLatheTarget = latheStepsPerStage * lathePressCount;
  
  // 방향이 반대이므로 음수(-) 전송
  latheStepper.step(-currentLatheTarget);
}

void returnLathe() {
  // 복귀 (양수)
  latheStepper.step(currentLatheTarget);
  
  // 모터 발열 방지를 위한 대기 전력 차단
  digitalWrite(A0, LOW);
  digitalWrite(A1, LOW);
  digitalWrite(A2, LOW);
  digitalWrite(A3, LOW);
}

// ===== 전체 배출 과정 =====
void processDispense(int floorIndex) {
  Serial.println("STATUS:MOVING");
  
  // 4층(선반 바이트)이 아닐 때만 수직 모터(엘리베이터) 이동
  if (floorIndex != 3) {
    moveVertical(floorSteps[floorIndex]);
  }
  
  Serial.println("STATUS:ARRIVED");
  delay(500);
  
  Serial.println("STATUS:PUSHING");
  // 4층 선반 바이트일 경우 L298N 구동, 나머지는 X축 A4988 구동
  if (floorIndex == 3) {
    pushLathe();
  } else {
    pushItem();
  }
  delay(500);
  
  Serial.println("STATUS:RETURNING");
  if (floorIndex == 3) {
    returnLathe();
  } else {
    returnPusher();
  }
  delay(500);
  
  // 4층(선반 바이트)이 아닐 때만 엘리베이터 1층 원점 복귀
  if (floorIndex != 3) {
    moveVertical(0);
  }
  
  Serial.println("STATUS:DONE");
}
