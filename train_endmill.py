from ultralytics import YOLO
import multiprocessing

if __name__ == '__main__':
    # Windows 환경에서 멀티프로세싱 에러 방지
    multiprocessing.freeze_support()

    print("🚀 최신 Ultralytics YOLO26 엔진으로 엔드밀 학습을 시작합니다...")
    
    # 최신 YOLO26 nano 모델 로드
    model = YOLO('yolo26n.pt')
    
    # 학습 시작
    results = model.train(
        data=r'C:\Users\USER\Desktop\qwert\endmill_dataset\data.yaml',
        epochs=50,         # 총 50번 반복 학습
        imgsz=640,         # 이미지 크기
        batch=16,          # 한 번에 처리할 이미지 수
        name='endmill_yolo26', # 저장될 모델 이름
        plots=True         # 학습 결과 그래프 생성
    )
    
    print("\n🎉 학습이 완료되었습니다! 결과는 runs/detect/endmill_yolo26 폴더에 저장되었습니다.")
