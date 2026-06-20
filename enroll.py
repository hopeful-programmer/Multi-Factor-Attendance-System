import os
import time
import ctypes
import cv2
import face_recognition as fr
import numpy
import pveagle
from pvrecorder import PvRecorder
from dotenv import load_dotenv
from user import User

load_dotenv()

userClass = User()

ACCESS_KEY = os.environ.get("PICOVOICE_ACCESS_KEY")
MIC_DEFAULT_DEVICE_INDEX = int(os.environ.get("MIC_DEVICE_INDEX", "-1"))
CAM_DEFAULT_DEVICE_INDEX = int(os.environ.get("CAM_DEVICE_INDEX", "0"))
FRAME_SCALE = 4  # process at 1/4 resolution for faster face detection

try:
    eagle_profiler = pveagle.create_profiler(ACCESS_KEY)
except pveagle.EagleError as e:
    print(e)
    exit(1)

recorder = PvRecorder(
    device_index=MIC_DEFAULT_DEVICE_INDEX,
    frame_length=eagle_profiler.frame_length
)


def showUsers():
    users = userClass.getAllUsers()
    print("#=========== Users =============#")
    print("user_id - name")
    for user in users:
        id, name, password, ff, ap, isActive = user
        print(str(id) + " - " + name)
    print("#===============================#")


def getUserCount():
    return len(userClass.getAllUsers())


def get_valid_name(prompt="Enter user's name: "):
    while True:
        name = input(prompt).strip()
        if len(name) < 2:
            print("Name must be at least 2 characters")
        elif not all(c.isalpha() or c in (" ", "-") for c in name):
            print("Name can only contain letters, spaces, and hyphens")
        else:
            return name


def get_valid_password(prompt="enter password: "):
    while True:
        password = input(prompt)
        if len(password) < 6:
            print("Password must be at least 6 characters")
        else:
            return password


def modifyUser():
    showUsers()
    while True:
        try:
            index = int(input("Enter user's id to modify or -1 to exit: "))
        except ValueError:
            print("Invalid input — enter a number")
            continue

        if index < 0:
            break

        op = input("enter property number to modify\n"
                   "1. Name\n"
                   "2. Password\n"
                   "3. Face features\n")

        match op:
            case '1':
                name = get_valid_name("enter the new user's name: ")
                userClass.updateUser(index, name=name)
                print("Name modified to " + name)
                break

            case '2':
                password = get_valid_password("enter the new password: ")
                userClass.updateUser(index, password=password)
                print("Password updated")
                break

            case '3':
                ff = getFaceEncoding()
                if ff:
                    userClass.updateUser(index, face_features=ff)
                    print("Face features modified")
                break

            case _:
                break


def getFaceEncoding():
    faceEncoding = None

    cam = None
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
        for _ in range(2):
            cam = cv2.VideoCapture(CAM_DEFAULT_DEVICE_INDEX, backend)
            if cam.isOpened():
                break
            cam.release()
            time.sleep(0.5)
        if cam.isOpened():
            break
        cam.release()

    if not cam or not cam.isOpened():
        print("Error: could not open webcam. Check that it is connected and not in use by another app.")
        return None

    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    try:
        for _ in range(5):
            cam.read()

        cv2.namedWindow("Face Capture", cv2.WINDOW_AUTOSIZE)

        def askForAcceptance(frame):
            cv2.imshow("Face Capture", frame)
            res = input("Do you want to use this picture? (y or n): ")
            if res == "y":
                encodings = fr.face_encodings(frame)
                if not encodings:
                    print("No face detected in the captured frame — try again")
                    return None
                return encodings[0]
            return None

        print("Press S when a purple box is shown around the face, or Q to exit")
        window_raised = False
        while True:
            ret, frame = cam.read()
            if not ret or frame is None:
                continue
            frameS = cv2.resize(frame, (0, 0), None, 1 / FRAME_SCALE, 1 / FRAME_SCALE)
            frame2 = frame.copy()
            allFacesLoc = fr.face_locations(frameS)
            for faceLoc in allFacesLoc:
                y1, x2, y2, x1 = faceLoc
                y1, x2, y2, x1 = y1 * FRAME_SCALE, x2 * FRAME_SCALE, y2 * FRAME_SCALE, x1 * FRAME_SCALE
                cv2.rectangle(frame2, (x1, y1), (x2, y2), (255, 0, 255), 2)

            cv2.imshow("Face Capture", frame2)

            if not window_raised:
                cv2.setWindowProperty("Face Capture", cv2.WND_PROP_TOPMOST, 1)
                hwnd = ctypes.windll.user32.FindWindowW(None, "Face Capture")
                if hwnd:
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                window_raised = True

            key = cv2.waitKey(1) & 0xFF
            if key == ord('s') and len(allFacesLoc) > 0:
                faceEncoding = askForAcceptance(frame)
                break
            if key == ord('q'):
                break
            if cv2.getWindowProperty("Face Capture", cv2.WND_PROP_VISIBLE) < 1:
                break

    finally:
        cam.release()
        cv2.destroyAllWindows()

    if isinstance(faceEncoding, numpy.ndarray):
        return str(faceEncoding.tolist()).replace("[", "").replace("]", "")


def getAudioEncoding(speaker_name):
    eagle_profiler.reset()
    print(f"\nSpeak naturally to create your voice profile.")
    print(f"Try: \"Hi, my name is {speaker_name}, and I'm creating my voice profile.\"")
    input("Press Enter when ready to start recording...")

    recorder.start()
    for _ in range(20):
        recorder.read()

    print("Recording — speak now!")
    enroll_percentage = 0.0
    while enroll_percentage < 100.0:
        audio_frame = recorder.read()
        enroll_percentage = eagle_profiler.enroll(audio_frame)
        print(f"\rEnrollment progress: {enroll_percentage:.1f}%", end="", flush=True)

    recorder.stop()
    print("\nVoice enrollment complete.")
    return eagle_profiler.export().to_bytes()


def isFaceAlreadyEnrolled(ff_str):
    ff_array = numpy.asarray(ff_str.split(", "), dtype=numpy.float64)
    for user in userClass.getAllUsers():
        _, existing_name, _, existing_ff, _, _ = user
        existing_array = numpy.asarray(existing_ff.split(", "), dtype=numpy.float64)
        if fr.face_distance([existing_array], ff_array)[0] < 0.5:
            return existing_name
    return None


def addUser():
    name = get_valid_name("enter the new user's name: ")

    inactive_id = userClass.getInactiveUserByName(name)
    if inactive_id:
        choice = input(f"'{name}' was previously removed. Re-enroll this user? (y/n): ").strip().lower()
        if choice != 'y':
            return
        password = get_valid_password("enter the new password: ")
        ff = getFaceEncoding()
        if not ff:
            print("Error: face enrollment failed, user not re-enrolled")
            return
        duplicate = isFaceAlreadyEnrolled(ff)
        if duplicate:
            print(f"Error: this face is already enrolled under '{duplicate}'")
            return
        ap = getAudioEncoding(name)
        userClass.reactivateUser(inactive_id, password, ff, ap)
        print(f"User '{name}' re-enrolled successfully")
        return

    existing_names = [user[1].lower() for user in userClass.getAllUsers()]
    if name.strip().lower() in existing_names:
        print(f"Error: a user named '{name}' is already enrolled")
        return

    password = get_valid_password("enter the new user's password: ")
    ff = getFaceEncoding()
    if not ff:
        print("Error: face enrollment failed, user not added")
        return

    duplicate = isFaceAlreadyEnrolled(ff)
    if duplicate:
        print(f"error: this face is already enrolled under '{duplicate}'")
        return

    ap = getAudioEncoding(name)

    if ff and ap:
        if userClass.addUser(name, password, ff, ap):
            print(f"User '{name}' added successfully")
        else:
            print("Error: user was not added")
    else:
        print("Error: face or voice enrollment failed")


def removeUser():
    showUsers()
    try:
        op = int(input("enter the user's id to remove: "))
    except ValueError:
        print("Invalid input — enter a number")
        return
    result = userClass.getOneUser(op)

    if result is None:
        print("No user found with this ID")
        return

    id, name, password, ff, ap, isActive = result
    if userClass.deleteUser(op):
        print(f"User '{name}' removed")
    else:
        print("Error: user was not deleted")


systemLoop = True
print("=== Attendance System — User Management ===\n")
try:
    while systemLoop:

        print(f"1. Show all users ({getUserCount()})\n"
              "2. Add new user\n"
              "3. Modify user\n"
              "4. Remove user\n"
              "5. Exit\n")

        op = input("Enter option: ")

        match op:
            case '1':
                showUsers()

            case '2':
                addUser()

            case '3':
                modifyUser()

            case '4':
                removeUser()

            case '5':
                print("Returning to main menu")
                break

            case _:
                print("\nInvalid option\n")

finally:
    recorder.delete()
    eagle_profiler.delete()
