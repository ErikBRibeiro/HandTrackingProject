import cv2
import time
import numpy as np
import math

# --- Hand tracking ---
import HandTrackingModule as htm

# --- Pycaw: API nova (precisa comtypes) ---
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

#################################################
wCam, hCam = 640, 480
# Distâncias (em pixels) para mapear → ajuste conforme tua câmera/posição
MIN_DIST = 40    # “pinch” (quase encostando)
MAX_DIST = 170   # bem afastado
# Histerese simples para 0% quando muito perto
PINCH_ZERO = 50
#################################################

# Webcam
cap = cv2.VideoCapture(0)
cap.set(3, wCam)
cap.set(4, hCam)

# Detector
detector = htm.handDetector(detectionCon=0.7)

# Pycaw
speakers = AudioUtilities.GetSpeakers()
interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
endpoint_volume = cast(interface, POINTER(IAudioEndpointVolume))

# Faixa em dB
# vmin_db, vmax_db, _ = endpoint_volume.GetVolumeRange()  # típ: (-65.25, 0.0, 0.03125)

# Estado
pTime = 0
vol_scalar = endpoint_volume.GetMasterVolumeLevelScalar()  # 0.0–1.0

while True:
    ok, img = cap.read()
    if not ok or img is None:
        continue

    img = detector.findHands(img)
    lmList, bbox = detector.findPosition(img, draw=False)

    if len(lmList) >= 9:  # garante 4 e 8 disponíveis
        # Pontas: 4 = polegar, 8 = indicador
        x1, y1 = lmList[4][1], lmList[4][2]
        x2, y2 = lmList[8][1], lmList[8][2]

        # Centro da linha (para feedback visual)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        # Desenho
        cv2.circle(img, (x1, y1), 12, (255, 0, 255), cv2.FILLED)
        cv2.circle(img, (x2, y2), 12, (255, 0, 255), cv2.FILLED)
        cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
        cv2.circle(img, (cx, cy), 10, (255, 0, 255), cv2.FILLED)

        # Distância euclidiana
        length = math.hypot(x2 - x1, y2 - y1)

        # Mapeamento → 0–100 (clamp) e depois para 0.0–1.0
        vol_pct = np.interp(length, [MIN_DIST, MAX_DIST], [0, 100])
        vol_pct = float(np.clip(vol_pct, 0, 100))

        # Pinch bem fechado → força 0% (feedback em verde)
        if length <= PINCH_ZERO:
            vol_pct = 0
            cv2.circle(img, (cx, cy), 12, (0, 255, 0), cv2.FILLED)

        vol_scalar = vol_pct / 100.0
        try:
            endpoint_volume.SetMasterVolumeLevelScalar(vol_scalar, None)
        except Exception:
            pass  # evita travar se o endpoint de áudio mudar

        # HUD: barra de volume
        bar_top, bar_bottom = 100, 400
        bar_y = int(np.interp(vol_pct, [0, 100], [bar_bottom, bar_top]))

        cv2.rectangle(img, (50, bar_top), (85, bar_bottom), (255, 0, 255), 2)
        cv2.rectangle(img, (50, bar_y), (85, bar_bottom), (255, 0, 255), cv2.FILLED)
        cv2.putText(img, f'{int(vol_pct)} %', (40, 430), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)

    # FPS
    cTime = time.time()
    fps = 1.0 / (cTime - pTime) if cTime != pTime else 0.0
    pTime = cTime
    cv2.putText(img, f'FPS: {int(fps)}', (10, 30), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 2)

    cv2.imshow("Volume Hand Control", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
