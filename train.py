from ultralytics import YOLO
import multiprocessing
import os

def main():
    # YOLO 모델 로드 (최신 YOLO26 nano 모델 - RTX 4060 8GB에 최적)
    model = YOLO("yolo26n.pt")

    # ====================================================================
    # [학습 모드 선택] 
    # 주의: 엔드밀과 선반 바이트의 파손 형태가 다르므로 2개의 AI 모델로 분리하여 학습했습니다.
    # 학습할 데이터셋에 맞춰 주석을 해제하여 번갈아 실행하세요.
    # ====================================================================
    
    # 1. 엔드밀 파손 검사 데이터셋 세팅 (기본)
    TARGET_DATASET = "C:/Users/USER/Desktop/qwert/qwert-1/data.yaml"
    TARGET_NAME = "endmill_yolo26"

    # 2. 선반 바이트 파손 검사 데이터셋 세팅 (학습 시 주석 해제)
    # TARGET_DATASET = "C:/Users/USER/Desktop/qwert/lathe_dataset/data.yaml"
    # TARGET_NAME = "lathe_yolo26"

    print(f"\n[{TARGET_NAME}] 커스텀 AI 모델 트레이닝을 시작합니다...")

    # 커스텀 트레이닝
    results = model.train(
        data=TARGET_DATASET,
        epochs=100,          # 학습 횟수
        imgsz=640,           # 이미지 크기
        batch=16,            # 배치 사이즈 (8GB VRAM 기준)
        patience=20,         # 20 epoch 동안 개선 없으면 조기 종료
        device=0,            # GPU 사용 (RTX 4060)
        workers=0,           # Windows 호환을 위해 0으로 설정
        project="runs/detect", # app.py에서 불러오는 경로와 일치시킴
        name=TARGET_NAME,    # 실험 이름 (엔드밀 / 선반 바이트 자동 분리)
        exist_ok=True,       # 같은 이름 덮어쓰기 허용
        verbose=True,        # 상세 로그 출력
    )

    print("\n✅ 트레이닝 완료!")
    print(f"결과 저장 경로: runs/detect/{TARGET_NAME}")
    print(f"최고 모델 적용 경로: runs/detect/{TARGET_NAME}/weights/best.pt")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
