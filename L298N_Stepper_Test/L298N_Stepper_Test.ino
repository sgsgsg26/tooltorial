#include <Stepper.h>

const int stepsPerRev = 200;
Stepper latheStepper(stepsPerRev, A0, A1, A2, A3);

// [중요] 12mm 전진에 필요한 스텝 수 (기계마다 달라서 튜닝이 필요합니다)
// 예: 1바퀴(200스텝) 돌 때 8mm 전진하는 스크류라면 12mm = 300스텝
int stepsPerStage = 1500; 

// 현재 몇 번째 누른 것인지 기억하는 변수
int pressCount = 0; 

void setup() {
  Serial.begin(9600);
  latheStepper.setSpeed(60); // 속도 
  
  pinMode(A0, OUTPUT);
  pinMode(A1, OUTPUT);
  pinMode(A2, OUTPUT);
  pinMode(A3, OUTPUT);
  
  Serial.println("=== 3단계 선반 바이트 배출 테스트 ===");
  Serial.println("T를 누를 때마다 1단계(12mm) -> 2단계(24mm) -> 3단계(36mm) 순으로 배출합니다.");
}

void powerOff() {
  digitalWrite(A0, LOW);
  digitalWrite(A1, LOW);
  digitalWrite(A2, LOW);
  digitalWrite(A3, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    
    if (cmd == 'T' || cmd == 't') {
      pressCount++;
      
      // 3번을 초과하면 다시 1번(12mm)부터 시작하도록 리셋
      if (pressCount > 3) {
        pressCount = 1;
      }
      
      // 이번에 이동해야 할 총 스텝 수 계산 (예: 2번째면 300 * 2 = 600스텝)
      int targetSteps = stepsPerStage * pressCount;
      
      Serial.print("\n["); 
      Serial.print(pressCount); 
      Serial.print("회차 배출] ");
      Serial.print(targetSteps); 
      Serial.println(" 스텝 전진 중...");
      
      // 방향이 반대라고 하셨으므로 전진을 음수(-)로 설정
      latheStepper.step(-targetSteps); 
      
      delay(1000); // 밀어내고 1초 대기
      
      Serial.println("원점 복귀 중...");
      // 전진한 만큼 양수(+)를 주어 정확히 제자리로 복귀
      latheStepper.step(targetSteps); 
      
      powerOff(); // 발열 방지
      Serial.println("배출 및 복귀 완료! (전력 차단됨)");
    }
  }
}
