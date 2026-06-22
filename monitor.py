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
failedVoiceAttempts = 0
failedPasswordAttempts = 0
sessionLocked = False
MAX_VOICE_ATTEMPTS = 2
MAX_PASSWORD_ATTEMPTS = 3


# --- Load enrolled users from database ---
userIds = []
names = []
encodedFacesList = []
audioProfilesList = []

try:
    users = userClass.getAllUsers()
except Exception as e:
    print(f"Error: could not connect to database — {e}")
    exit(1)

for user in users:
    id, name, password, ff, ap, isActive = user
    ff = ff.split(", ")
    ff = np.asarray(ff, dtype=np.float64)
    ap = pveagle.EagleProfile.from_bytes(ap)

    userIds.append(id)
    names.append(name)
    encodedFacesList.append(ff)
    audioProfilesList.append(ap)

if not names:
    print("No users enrolled — enroll user first.")
    exit(0)

print(f"Loaded {len(names)} enrolled users: {names}")


try:
    eagle = pveagle.create_recognizer(ACCESS_KEY)
except pveagle.EagleError as e:
    print(e)
    exit(1)

recorder = PvRecorder(
    device_index=DEFAULT_DEVICE_INDEX,
    frame_length=eagle.min_process_samples)


cam = None
for _backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
    for _ in range(2):
        cam = cv2.VideoCapture(CAM_DEVICE_INDEX, _backend)
        if cam.isOpened():
            break
        cam.release()
        time.sleep(0.5)
    if cam.isOpened():
        break
    cam.release()

if not cam or not cam.isOpened():
    print("Error: could not open webcam. Check that it is connected and not in use by another app.")
    exit(1)

for _ in range(5):
    cam.read()

cv2.namedWindow('Attendance Monitor', cv2.WINDOW_AUTOSIZE)
cv2.setWindowProperty('Attendance Monitor', cv2.WND_PROP_TOPMOST, 1)


def verifyVoice(faceMatchIndex):
    global faceDetected, faceDetectedCounter

    print(f"Verifying voice for {names[faceMatchIndex]}...")
    startTime = time.time()
    recorder.start()
    verified = False

    try:
        while (time.time() - startTime) < 5:
            audio_frame = recorder.read()
            scores = eagle.process(audio_frame, audioProfilesList)
            if scores is None:
                continue
            audioMatchIndex = np.argmax(scores)
            if scores[audioMatchIndex] > 0.8 and audioMatchIndex == faceMatchIndex:
                print(f"{names[audioMatchIndex]} verified")
                verified = True
                break
    except (KeyboardInterrupt, ValueError):
        pass
    finally:
        faceDetectedCounter = 0
        recorder.stop()

    if not verified:
        print("Voice verification failed")
    return verified


def passwordFallback(suggested_name=""):
    global failedPasswordAttempts, sessionLocked

    if sessionLocked:
        print("System locked — restart the monitor to allow access.")
        return

    prompt = f"Name (press Enter for '{suggested_name}'): " if suggested_name else "Name: "
    while not sessionLocked:
        name = input(prompt).strip() or suggested_name
        password = input("Password: ").strip()

        if userClass.markAttended(credential=(name, password)):
            failedPasswordAttempts = 0
            return

        failedPasswordAttempts += 1
        if failedPasswordAttempts >= MAX_PASSWORD_ATTEMPTS:
            sessionLocked = True
            userClass.logSecurityEvent(name, "3 consecutive failed password attempts after biometric failure")
            print("Security alert: maximum failed attempts reached. Monitor locked until restart.")
        else:
            remaining = MAX_PASSWORD_ATTEMPTS - failedPasswordAttempts
            print(f"{remaining} attempt(s) remaining before lockout.")


print("=== Attendance Monitor Running — press Q to quit ===")

try:
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
            recognized = False

            if encodedFacesList:
                encodedFrame = fr.face_encodings(frameS, [faceLoc])
                if encodedFrame:
                    faceDis = fr.face_distance(encodedFacesList, encodedFrame[0])
                    if faceDis.min() < 0.5:
                        recognized = True
                        faceNotDetectedCounter = 0
                        matchIndex = np.argmin(faceDis)
                        name = names[matchIndex]

                        if faceDetected != name:
                            faceDetected = name
                            faceDetectedCounter = 0
                            failedVoiceAttempts = 0

                        faceDetectedCounter += 1
                        progress = round((faceDetectedCounter / 11) * 100, 1)
                        txt = f"{name} {progress}%"
                        y1, x2, y2, x1 = faceLoc
                        y1, x2, y2, x1 = y1 * FRAME_SCALE, x2 * FRAME_SCALE, y2 * FRAME_SCALE, x1 * FRAME_SCALE
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
                        cv2.rectangle(frame, (x1, y2 - 35), (x2, y2), (255, 0, 255), cv2.FILLED)
                        cv2.putText(frame, txt, (x1, y2 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

            if not recognized:
                faceNotDetectedCounter += 1
                y1, x2, y2, x1 = faceLoc
                y1, x2, y2, x1 = y1 * FRAME_SCALE, x2 * FRAME_SCALE, y2 * FRAME_SCALE, x1 * FRAME_SCALE
                cv2.rectangle(frame, (x1, y2 - 35), (x2, y2), (255, 0, 255), cv2.FILLED)
                cv2.putText(frame, "unknown", (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_DUPLEX, 1, (255, 255, 255), 2)

        if faceDetectedCounter > 11:
            faceDetectedCounter = 0
            if verifyVoice(matchIndex):
                failedVoiceAttempts = 0
                userClass.markAttended(id=userIds[matchIndex])
            else:
                failedVoiceAttempts += 1
                if failedVoiceAttempts >= MAX_VOICE_ATTEMPTS:
                    failedVoiceAttempts = 0
                    print("\nVoice verification failed — switching to password fallback")
                    passwordFallback(suggested_name=names[matchIndex])

        if faceNotDetectedCounter > 10:
            faceNotDetectedCounter = 0
            print("\nFace not recognized — switching to password fallback")
            passwordFallback()

        cv2.imshow('Attendance Monitor', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        if cv2.getWindowProperty("Attendance Monitor", cv2.WND_PROP_VISIBLE) < 1:
            break

finally:
    recorder.delete()
    eagle.delete()
    cam.release()
    cv2.destroyAllWindows()
