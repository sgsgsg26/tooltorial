from ultralytics import YOLO
import multiprocessing

def main():
    # YOLO 모델 로드 (nano 모델 - RTX 4060 8GB에 최적)
    model = YOLO("yolo11n.pt")

    # 커스텀 트레이닝
    results = model.train(
        data="C:/Users/USER/Desktop/qwert/qwert-1/data.yaml",
        epochs=100,          # 학습 횟수
        imgsz=640,           # 이미지 크기
        batch=16,            # 배치 사이즈 (8GB VRAM 기준)
        patience=20,         # 20 epoch 동안 개선 없으면 조기 종료
        device=0,            # GPU 사용 (RTX 4060)
        workers=0,           # Windows 호환을 위해 0으로 설정
        project="runs",      # 결과 저장 폴더
        name="yolo_custom",  # 실험 이름
        exist_ok=True,       # 같은 이름 덮어쓰기 허용
        verbose=True,        # 상세 로그 출력
    )

    print("\n✅ 트레이닝 완료!")
    print(f"결과 저장 경로: runs/yolo_custom")
    print(f"최고 모델: runs/yolo_custom/weights/best.pt")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
