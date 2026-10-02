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
import json
import urllib.request
import csv
import glob
from datetime import datetime

# .env 파일 수동 로드 (python-dotenv 의존성 제거)
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#") and "=" in line:
                key, val = line.strip().split("=", 1)
                os.environ[key.strip()] = val.strip()

from flask import Flask, jsonify, Response, request
from ultralytics import YOLO
import multiprocessing

# ============================================================
# 설정
# ============================================================
ENDMILL_MODEL_PATH = os.path.join(os.path.dirname(__file__), "runs", "detect", "endmill_yolo26", "weights", "best.pt")
LATHE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "runs", "detect", "lathe_yolo26", "weights", "best.pt")

# 민감도(신뢰도) 설정 (숫자가 낮을수록 예민하게 다 잡아냄)
ENDMILL_CONF_THRESHOLD = 0.20  # 엔드밀: 기본
LATHE_CONF_THRESHOLD = 0.15    # 선반바이트: 매우 예민하게 (0.05)


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
            # 실시간 YOLO 추론 적용
            if active_camera_model == "lathe" and lathe_model is not None:
                results = lathe_model.predict(source=frame, conf=LATHE_CONF_THRESHOLD, verbose=False)
                annotated = results[0].plot()
            elif active_camera_model == "endmill" and endmill_model is not None:
                results = endmill_model.predict(source=frame, conf=ENDMILL_CONF_THRESHOLD, verbose=False)
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
# YOLO 모델 (듀얼)
# ============================================================
endmill_model = None
lathe_model = None


CLASS_INFO = {
    "160": {"emoji": "✅", "label": "완벽한 양품입니다. 수령하세요.", "color": "#38a169"},
    "161": {"emoji": "⚠️", "label": "날 1개 파손이 의심됩니다.", "color": "#d69e2e"},
    "162": {"emoji": "❌", "label": "날 2개 이상 파손이 의심됩니다. 폐기처리가 필요합니다.", "color": "#e53e3e"},
    
    "140": {"emoji": "✅", "label": "완벽한 양품입니다. 수령하세요.", "color": "#38a169"},
    "141": {"emoji": "⚠️", "label": "날 1개 파손이 의심됩니다.", "color": "#d69e2e"},
    "142": {"emoji": "❌", "label": "날 2개 이상 파손이 의심됩니다. 폐기처리가 필요합니다.", "color": "#e53e3e"},
    
    "120": {"emoji": "✅", "label": "완벽한 양품입니다. 수령하세요.", "color": "#38a169"},
    "121": {"emoji": "⚠️", "label": "날 1개 파손이 의심됩니다.", "color": "#d69e2e"},
    "122": {"emoji": "❌", "label": "날 2개 이상 파손이 의심됩니다. 폐기처리가 필요합니다.", "color": "#e53e3e"},
    
    "lathe_0": {"emoji": "✅", "label": "완벽한 양품입니다. 수령하세요.", "color": "#38a169"},
    "lathe_1": {"emoji": "⚠️", "label": "날 1개 파손이 의심됩니다.", "color": "#d69e2e"},
    "lathe_2": {"emoji": "❌", "label": "날 2개 이상 파손이 의심됩니다. 폐기처리가 필요합니다.", "color": "#e53e3e"},
}

def load_model():
    global endmill_model, lathe_model
    try:
        endmill_model = YOLO(ENDMILL_MODEL_PATH)
        lathe_model = YOLO(LATHE_MODEL_PATH)
        print("[YOLO] 엔드밀 및 선반 바이트 모델 로드 완료!")
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

active_camera_model = "endmill"

@app.route("/api/set_camera_model", methods=["POST"])
def set_camera_model():
    global active_camera_model
    data = request.json or {}
    tool = data.get("tool", "")
    if "4층" in tool or "바이트" in tool:
        active_camera_model = "lathe"
    else:
        active_camera_model = "endmill"
    return jsonify({"success": True})

@app.route("/video_feed")
def video_feed():
    """실시간 카메라 스트리밍 엔드포인트"""
    return Response(generate_stream(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route("/api/ogq-stickers")
def get_ogq_stickers():
    api_key = os.environ.get("OGQ_API_KEY", "")
    if not api_key:
        return jsonify({"success": False, "message": "API Key not found in .env"}), 400
    try:
        req = urllib.request.Request("https://4th-ai-ogq.competition.ogq.me/v1/assets?pageSize=38", headers={"X-OGQ-API-KEY": api_key})
        res = urllib.request.urlopen(req, timeout=5)
        data = json.loads(res.read())
        urls = [el.get("thumbnailUrl") for el in data.get("elements", []) if el.get("thumbnailUrl")]
        return jsonify({"success": True, "urls": urls})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/detect")
def detect():
    tool = request.args.get('tool', '')
    is_lathe = ("4층" in tool or "바이트" in tool)
    
    target_model = lathe_model if is_lathe else endmill_model
    current_conf = LATHE_CONF_THRESHOLD if is_lathe else ENDMILL_CONF_THRESHOLD
    
    if target_model is None:
        return jsonify({"success": False, "message": "모델이 로드되지 않았습니다."}), 500

    with camera_lock:
        if current_frame is None:
            return jsonify({"success": False, "message": "카메라가 준비되지 않았습니다."}), 500
        frame = current_frame.copy()

    results = target_model.predict(
        source=frame,
        conf=current_conf,
        verbose=False,
    )
    result = results[0]

    real_detections = []
    for box in result.boxes:
        cls_id = int(box.cls[0])
        cls_name = result.names[cls_id]
        confidence = float(box.conf[0])
        info = CLASS_INFO.get(cls_name, {"label": cls_name, "color": "#6b7280", "emoji": "❓"})
        real_detections.append({
            "class": cls_name,
            "label": info["label"],
            "color": info["color"],
            "emoji": info["emoji"],
            "confidence": round(confidence * 100, 1),
        })

    real_detections.sort(key=lambda x: x["confidence"], reverse=True)
    final_detections = real_detections

    annotated = result.plot()
    
    save_path = os.path.join(os.path.dirname(__file__), "latest_detection.jpg")
    cv2.imwrite(save_path, annotated)
    
    gallery_path = os.path.join(
        os.path.dirname(__file__), "detection_gallery",
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    )
    cv2.imwrite(gallery_path, annotated)

    _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
    img_b64 = base64.b64encode(buffer).decode("utf-8")
    
    return jsonify({
        "success": True,
        "detections": final_detections,
        "image": img_b64
    })

@app.route("/api/health")
def health():
    """서버 상태 확인"""
    return jsonify({
        "status": "ok",
        "model_loaded": (endmill_model is not None and lathe_model is not None),
    })

# ============================================================
# 관리자 대시보드 - 이벤트 로깅 시스템
# ============================================================
EVENT_LOG_PATH = os.path.join(os.path.dirname(__file__), "event_logs.csv")
DETECTION_IMG_DIR = os.path.join(os.path.dirname(__file__), "detection_gallery")
os.makedirs(DETECTION_IMG_DIR, exist_ok=True)

# 인메모리 이벤트 저장소 (서버 시작 시 CSV에서 로드)
event_store = []
event_lock = threading.Lock()

# 재고 현황 (층별 초기 재고)
stock = {1: 10, 2: 10, 3: 10, 4: 10}

def load_events_from_csv():
    """서버 시작 시 기존 CSV 로그를 메모리로 로드"""
    global event_store
    if os.path.exists(EVENT_LOG_PATH):
        try:
            with open(EVENT_LOG_PATH, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                event_store = list(reader)
            print(f"[Dashboard] 기존 로그 {len(event_store)}건 로드 완료")
        except Exception as e:
            print(f"[Dashboard] 로그 로드 실패: {e}")
            event_store = []

def save_event(event):
    """이벤트를 메모리와 CSV에 동시 저장"""
    with event_lock:
        event_store.append(event)
        file_exists = os.path.exists(EVENT_LOG_PATH)
        with open(EVENT_LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "timestamp", "user_id", "event_type", "tool_type", "floor", 
                "ai_result", "ai_confidence", "detail"
            ])
            if not file_exists:
                writer.writeheader()
            writer.writerow(event)

@app.route("/admin")
def admin_page():
    """관리자 대시보드 페이지"""
    return app.send_static_file("admin.html")

@app.route("/api/log", methods=["POST"])
def log_event():
    """사용자 UI에서 이벤트를 기록하는 API"""
    data = request.get_json(force=True)
    event = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": data.get("user_id", "Unknown"),
        "event_type": data.get("event_type", ""),
        "tool_type": data.get("tool_type", ""),
        "floor": data.get("floor", ""),
        "ai_result": data.get("ai_result", ""),
        "ai_confidence": data.get("ai_confidence", ""),
        "detail": data.get("detail", "")
    }
    save_event(event)
    
    # 배출 완료 시 재고 차감
    if event["event_type"] == "완료" and event["floor"]:
        floor_num = int(event["floor"])
        if floor_num in stock and stock[floor_num] > 0:
            stock[floor_num] -= 1
    
    print(f"[Dashboard] 이벤트 기록: {event['event_type']} - {event['user_id']}")
    return jsonify({"success": True})

@app.route("/api/logs/reset", methods=["POST"])
def reset_logs():
    with event_lock:
        event_store.clear()
    return jsonify({"success": True})

@app.route("/api/dashboard-stats")
def dashboard_stats():
    """관리자 대시보드용 통계 데이터"""
    with event_lock:
        logs = list(event_store)
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_logs = [e for e in logs if e.get("timestamp", "").startswith(today)]
    
    # 오늘 배출 완료 건수
    today_complete = [e for e in today_logs if e.get("event_type") == "완료"]
    today_total = len(today_complete)
    
    # AI 판독 결과 통계 (전체)
    all_complete = [e for e in logs if e.get("event_type") == "완료" and e.get("ai_result")]
    ai_results = {"Good": 0, "One Broken": 0, "Two Broken": 0, "Broken": 0}
    for e in all_complete:
        r = str(e.get("ai_result", ""))
        mapped_r = "Good"
        if r.endswith("1"): mapped_r = "One Broken"
        elif r.endswith("2"): mapped_r = "Broken"
        elif r == "Broken": mapped_r = "Broken"
        elif r == "One Broken": mapped_r = "One Broken"
        elif r == "Two Broken": mapped_r = "Two Broken"
        
        ai_results[mapped_r] += 1
    
    total_ai = sum(ai_results.values())
    ai_good_rate = round((ai_results["Good"] / total_ai * 100), 1) if total_ai > 0 else 0
    damage_count = total_ai - ai_results["Good"]
    
    # 공구 종류별 배출 통계
    tool_dist = {}
    for e in all_complete:
        t = e.get("tool_type", "기타")
        tool_dist[t] = tool_dist.get(t, 0) + 1
    
    # 시간대별 사용량 (0~23시)
    hourly = [0] * 24
    for e in all_complete:
        try:
            h = int(e.get("timestamp", "00:00:00").split(" ")[1].split(":")[0])
            hourly[h] += 1
        except:
            pass
    
    # 알림 생성
    alerts = []
    for floor_num, qty in stock.items():
        floor_names = {1: "16파이 엔드밀", 2: "14파이 엔드밀", 3: "12파이 엔드밀", 4: "선반 바이트"}
        if qty <= 2:
            alerts.append({
                "type": "warning",
                "icon": "⚠️",
                "message": f"{floor_num}층 {floor_names.get(floor_num, '')} 잔량 {qty}개 - 보충 필요!"
            })
    if damage_count >= 3:
        alerts.append({
            "type": "danger",
            "icon": "🔴",
            "message": f"파손 의심 공구 누적 {damage_count}건 - 입고 품질 점검 필요"
        })
    alerts.append({
        "type": "success",
        "icon": "✅",
        "message": "AI 모델 및 카메라 시스템 정상 가동 중"
    })
    
    # 최근 로그 20건 (최신순)
    recent = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)[:20]
    
    return jsonify({
        "today_total": today_total,
        "ai_good_rate": ai_good_rate,
        "damage_count": damage_count,
        "stock": stock,
        "tool_distribution": tool_dist,
        "hourly_usage": hourly,
        "ai_results": ai_results,
        "alerts": alerts,
        "recent_logs": recent,
        "total_events": len(logs)
    })

@app.route("/api/recent-detections")
def recent_detections():
    """최근 AI 판독 이미지 갤러리"""
    images = []
    # detection_gallery 폴더에서 최근 이미지 6장
    img_files = sorted(glob.glob(os.path.join(DETECTION_IMG_DIR, "*.jpg")), reverse=True)[:6]
    for img_path in img_files:
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        images.append({
            "filename": os.path.basename(img_path),
            "image": img_b64
        })
    
    # 갤러리에 이미지가 없으면 latest_detection.jpg라도 보여줌
    if not images:
        latest_path = os.path.join(os.path.dirname(__file__), "latest_detection.jpg")
        if os.path.exists(latest_path):
            with open(latest_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
            images.append({"filename": "latest_detection.jpg", "image": img_b64})
    
    return jsonify({"images": images})

@app.route("/api/stock/reset", methods=["POST"])
def reset_stock():
    """재고 초기화 (보충 시 사용)"""
    global stock
    stock = {1: 10, 2: 10, 3: 10, 4: 10}
    return jsonify({"success": True, "stock": stock})

if __name__ == "__main__":
    multiprocessing.freeze_support()

    print("=" * 50)
    print("  YOLO 추론 API 서버 (스트리밍 지원)")
    print("=" * 50)

    load_model()
    load_events_from_csv()
    
    # 카메라 스레드 시작
    t = threading.Thread(target=camera_thread, daemon=True)
    t.start()

    print("\n[Server] http://localhost:5000 에서 실행 중...")
    print("[Server] UI: http://localhost:5000/endmill-vending-ui.html")
    print("[Server] 관리자: http://localhost:5000/admin")
    print("=" * 50)

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
