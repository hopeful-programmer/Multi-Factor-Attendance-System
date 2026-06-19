import os
import time

import cv2
import face_recognition as fr
import numpy as np
from dotenv import load_dotenv
import pveagle
from pvrecorder import PvRecorder
from user import User

load_dotenv()

userClass = User()
ACCESS_KEY = os.environ.get("PICOVOICE_ACCESS_KEY")
DEFAULT_DEVICE_INDEX = int(os.environ.get("MIC_DEVICE_INDEX", "-1"))
CAM_DEVICE_INDEX = int(os.environ.get("CAM_DEVICE_INDEX", "0"))
FRAME_SCALE = 4  # process at 1/4 resolution for faster face detection

faceDetected = ""
faceDetectedCounter = 0
faceNotDetectedCounter = 0
failedPasswordAttempts = 0
lockoutStartTime = None
MAX_PASSWORD_ATTEMPTS = 3
LOCKOUT_SECONDS = 60


# --- Load enrolled users from database ---
userIds = []
names = []
encodedFacesList = []
audioProfilesList = []

users = userClass.getAllUsers()

for user in users:
    id, name, password, ff, ap, isActive = user
    ff = ff.split(", ")
    ff = np.asarray(ff, dtype=np.float64)
    ap = pveagle.EagleProfile.from_bytes(ap)

    userIds.append(id)
    names.append(name)
    encodedFacesList.append(ff)
    audioProfilesList.append(ap)

print(f"Loaded {len(names)} enrolled users: {names}")


try:
    eagle = pveagle.create_recognizer(ACCESS_KEY)
except pveagle.EagleError as e:
    print(e)
    exit(1)

recorder = PvRecorder(
    device_index=DEFAULT_DEVICE_INDEX,
    frame_length=eagle.min_process_samples)


cam = cv2.VideoCapture(CAM_DEVICE_INDEX, cv2.CAP_DSHOW)
if not cam.isOpened():
    print("Error: could not open webcam. Check that it is connected and not in use by another app.")
    exit(1)


def verifyVoice(faceMatchIndex):
    global faceDetected, faceDetectedCounter

    print(f"Verifying voice for {names[faceMatchIndex]}...")
    startTime = time.time()
    recorder.start()

    try:
        while (time.time() - startTime) < 5:
            audio_frame = recorder.read()
            scores = eagle.process(audio_frame, audioProfilesList)
            if scores is None:
                continue
            audioMatchIndex = np.argmax(scores)
            if scores[audioMatchIndex] > 0.8 and audioMatchIndex == faceMatchIndex:
                print(f"{names[audioMatchIndex]} verified")
                faceDetected = ""
                faceDetectedCounter = 0
                recorder.stop()
                return True

    except KeyboardInterrupt:
        pass

    faceDetected = ""
    faceDetectedCounter = 0
    recorder.stop()
    print("Voice verification failed")
    return False


print("=== Attendance Monitor Running — press Q to quit ===")

while True:
    ret, frame = cam.read()
    if not ret or frame is None:
        continue
    frameS = cv2.resize(frame, (0, 0), None, 1 / FRAME_SCALE, 1 / FRAME_SCALE)
    name = ""
    matchIndex = -1

    faceLoc = fr.face_locations(frameS)
    if faceLoc:
        faceLoc = faceLoc[0]
        encodedFrame = fr.face_encodings(frameS, [faceLoc])
        faceDis = fr.face_distance(encodedFacesList, encodedFrame[0])

        if faceDis.min() < 0.5:
            faceNotDetectedCounter = 0
            matchIndex = np.argmin(faceDis)
            name = names[matchIndex]

            if faceDetected == name:
                faceDetectedCounter += 1
            else:
                faceDetected = name
                faceDetectedCounter = 0

            faceDetectedCounter += 1
            progress = round((faceDetectedCounter / 11) * 100, 1)
            txt = f"{name} {progress}%"
            y1, x2, y2, x1 = faceLoc
            y1, x2, y2, x1 = y1 * FRAME_SCALE, x2 * FRAME_SCALE, y2 * FRAME_SCALE, x1 * FRAME_SCALE
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
            cv2.rectangle(frame, (x1, y2 - 35), (x2, y2), (255, 0, 255), cv2.FILLED)
            cv2.putText(frame, txt, (x1, y2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        else:
            faceNotDetectedCounter += 1
            y1, x2, y2, x1 = faceLoc
            y1, x2, y2, x1 = y1 * FRAME_SCALE, x2 * FRAME_SCALE, y2 * FRAME_SCALE, x1 * FRAME_SCALE
            cv2.rectangle(frame, (x1, y2 - 35), (x2, y2), (255, 0, 255), cv2.FILLED)
            cv2.putText(frame, "unknown", (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255), 2)

    if faceDetectedCounter > 11:
        faceDetectedCounter = 0
        if verifyVoice(matchIndex):
            userClass.markAttended(id=userIds[matchIndex])

    if faceNotDetectedCounter > 10:
        faceNotDetectedCounter = 0
        # module-level variables; no global declaration needed at top-level

        if lockoutStartTime is not None:
            elapsed = time.time() - lockoutStartTime
            remaining = int(LOCKOUT_SECONDS - elapsed)
            if elapsed < LOCKOUT_SECONDS:
                print(f"Too many failed attempts. Try again in {remaining} seconds.")
            else:
                failedPasswordAttempts = 0
                lockoutStartTime = None

        if lockoutStartTime is None:
            print("Face not recognized — switching to password fallback")
            name = input("name: ").strip()
            password = input("password: ").strip()
            success = userClass.markAttended(credential=(name, password))

            if success:
                failedPasswordAttempts = 0
            else:
                failedPasswordAttempts += 1
                remaining = MAX_PASSWORD_ATTEMPTS - failedPasswordAttempts
                if failedPasswordAttempts >= MAX_PASSWORD_ATTEMPTS:
                    lockoutStartTime = time.time()
                    print(f"Too many failed attempts. Locked out for {LOCKOUT_SECONDS} seconds.")
                else:
                    print(f"{remaining} attempt(s) remaining before lockout.")

    cv2.imshow('Attendance Monitor', frame)
    if cv2.waitKey(1) == ord('q'):
        break

    if cv2.getWindowProperty("Attendance Monitor", cv2.WND_PROP_VISIBLE) < 1:
        break


recorder.delete()
eagle.delete()
cam.release()
cv2.destroyAllWindows()
