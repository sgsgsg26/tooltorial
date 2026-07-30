"""
YOLO 추론 전용 API 서버
- 웹캠 캡처 + YOLO 추론만 담당
- 실시간 웹캠 영상 스트리밍 추가 (/video_feed)
"""
import cv2
import base64
import os
import threading
import time
from flask import Flask, jsonify, Response
from ultralytics import YOLO
import multiprocessing

# ============================================================
# 설정
# ============================================================
YOLO_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "runs", "detect", "runs", "yolo_custom", "weights", "best.pt"
)
CONFIDENCE_THRESHOLD = 0.35

# ============================================================
# Flask 앱
# ============================================================
app = Flask(__name__, static_folder=".", static_url_path="")
# CORS 허용 (로컬 HTML 파일에서 접근 가능)
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

# ============================================================
# 카메라 스레드 (스트리밍 및 캡처용)
# ============================================================
camera_lock = threading.Lock()
current_frame = None
stream_frame = None

def camera_thread():
    global current_frame, stream_frame
    cap = None
    for idx in [1, 2, 0]:
        temp_cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if temp_cap.isOpened():
            # 카메라 해상도를 강제로 HD급으로 올려서 미세 파손을 잘 잡도록 설정
            temp_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            temp_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap = temp_cap
            print(f"[Camera] 카메라 연결 성공: 인덱스 {idx}")
            break

    if cap is None or not cap.isOpened():
        print("[Camera] 에러: 카메라를 열 수 없습니다.")
        return

    while True:
        ret, frame = cap.read()
        if ret:
            # 실시간 YOLO 추론 적용 (스트리밍 화면용)
            if yolo_model is not None:
                results = yolo_model.predict(source=frame, conf=CONFIDENCE_THRESHOLD, device=0, verbose=False)
                annotated = results[0].plot()
            else:
                annotated = frame

            with camera_lock:
                current_frame = frame.copy()
                stream_frame = annotated.copy()
        time.sleep(0.03) # 약 30fps

def generate_stream():
    """MJPEG 스트리밍 생성기"""
    while True:
        with camera_lock:
            if stream_frame is None:
                frame_to_encode = None
            else:
                frame_to_encode = stream_frame.copy()
        
        if frame_to_encode is not None:
            ret, buffer = cv2.imencode('.jpg', frame_to_encode, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.05) # 약 20fps 스트리밍

# ============================================================
# YOLO 모델
# ============================================================
yolo_model = None

CLASS_INFO = {
    "good":         {"label": "양품 (Good)",         "color": "#3dd68c", "emoji": "✅"},
    "little":       {"label": "미세 손상 (Little)",   "color": "#f0a030", "emoji": "⚠️"},
    "destroyed":    {"label": "파손 (Destroyed)",     "color": "#ef4444", "emoji": "❌"},
    "double break": {"label": "이중 파손 (Double)",   "color": "#dc2626", "emoji": "🚨"},
    "qwert":        {"label": "기타 (Qwert)",         "color": "#8b5cf6", "emoji": "🔍"},
}

def load_model():
    global yolo_model
    try:
        yolo_model = YOLO(YOLO_MODEL_PATH)
        print(f"[YOLO] 모델 로드 완료: {YOLO_MODEL_PATH}")
        return True
    except Exception as e:
        print(f"[YOLO] 모델 로드 실패: {e}")
        return False


# ============================================================
# API 엔드포인트
# ============================================================
@app.route("/")
def index():
    """메인 UI 페이지 제공"""
    return app.send_static_file("endmill-vending-ui.html")

@app.route("/video_feed")
def video_feed():
    """실시간 카메라 스트리밍 엔드포인트"""
    return Response(generate_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/detect")
def detect():
    """웹캠 캡처 → YOLO 추론 → 결과 반환"""
    if yolo_model is None:
        return jsonify({"success": False, "message": "모델이 로드되지 않았습니다"}), 500

    # 현재 프레임 복사
    with camera_lock:
        if current_frame is None:
            return jsonify({"success": False, "message": "카메라 프레임이 준비되지 않았습니다"}), 500
        frame = current_frame.copy()

    # YOLO 추론
    results = yolo_model.predict(
        source=frame,
        conf=CONFIDENCE_THRESHOLD,
        device=0,
        verbose=False,
    )
    result = results[0]

    # 탐지 결과 파싱
    detections = []
    for box in result.boxes:
        cls_id = int(box.cls[0])
        cls_name = result.names[cls_id]
        confidence = float(box.conf[0])
        info = CLASS_INFO.get(cls_name, {"label": cls_name, "color": "#6b7280", "emoji": "?"})
        detections.append({
            "class": cls_name,
            "label": info["label"],
            "color": info["color"],
            "emoji": info["emoji"],
            "confidence": round(confidence * 100, 1),
        })

    # 신뢰도(confidence)가 높은 순으로 정렬
    detections.sort(key=lambda x: x["confidence"], reverse=True)

    # 결과 이미지 (바운딩 박스 포함)
    annotated = result.plot()
    
    # 디버깅용: 방금 검사한 이미지를 파일로 저장
    save_path = os.path.join(os.path.dirname(__file__), "latest_detection.jpg")
    cv2.imwrite(save_path, annotated)

    _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
    img_base64 = base64.b64encode(buffer).decode("utf-8")

    return jsonify({
        "success": True,
        "image": img_base64,
        "detections": detections,
    })


@app.route("/api/health")
def health():
    """서버 상태 확인"""
    return jsonify({
        "status": "ok",
        "model_loaded": yolo_model is not None,
    })


# ============================================================
# 메인
# ============================================================
if __name__ == "__main__":
    multiprocessing.freeze_support()

    print("=" * 50)
    print("  YOLO 추론 API 서버 (스트리밍 지원)")
    print("=" * 50)

    load_model()
    
    # 카메라 스레드 시작
    t = threading.Thread(target=camera_thread, daemon=True)
    t.start()

    print("\n[Server] http://localhost:5000 에서 실행 중...")
    print("[Server] UI: http://localhost:5000/endmill-vending-ui.html")
    print("=" * 50)

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
