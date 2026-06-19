import os
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


def modifyUser():
    showUsers()
    while True:
        index = int(input("enter user's id to modify or -1 to exit: "))

        if index < 0:
            break

        op = input("enter property number to modify\n"
                   "1. name\n"
                   "2. face features\n")

        match op:
            case '1':
                name = input("enter the new user's name: ")
                userClass.updateUser(index, name=name)
                print("name modified to " + name)
                break

            case '2':
                ff = getFaceEncoding()
                if ff:
                    userClass.updateUser(index, face_features=ff)
                    print("face features modified")
                break

            case _:
                break


def getFaceEncoding():
    faceEncoding = None

    cam = cv2.VideoCapture(CAM_DEFAULT_DEVICE_INDEX, cv2.CAP_DSHOW)
    if not cam.isOpened():
        print("Error: could not open webcam. Check that it is connected and not in use by another app.")
        return None

    cv2.namedWindow("Face Capture", cv2.WINDOW_AUTOSIZE)
    cv2.setWindowProperty("Face Capture", cv2.WND_PROP_TOPMOST, 1)

    def askForAcceptance(frame):
        cv2.imshow("Face Capture", frame)
        res = input("do you want to use this picture? (y or n): ")
        if res == "y":
            return fr.face_encodings(frame)[0]
        return None

    print("press S when a purple box is shown around the face")
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
        key = cv2.waitKey(1)
        if key == ord('s') and len(allFacesLoc) > 0:
            faceEncoding = askForAcceptance(frame)
            break
        if key == ord('q'):
            break
        if cv2.getWindowProperty("Face Capture", cv2.WND_PROP_VISIBLE) < 1:
            break

    cam.release()
    cv2.destroyAllWindows()

    if isinstance(faceEncoding, numpy.ndarray):
        return str(faceEncoding.tolist()).replace("[", "").replace("]", "")


def getAudioEncoding(speaker_name):
    eagle_profiler.reset()
    recorder.start()
    print(f"\nSpeak naturally to create your voice profile.")
    print(f"Try: \"Hi, my name is {speaker_name}, and I'm creating my voice profile.\"\n")
    enroll_percentage = 0.0
    while enroll_percentage < 100.0:
        audio_frame = recorder.read()
        enroll_percentage = eagle_profiler.enroll(audio_frame)
        print(f"\rEnrollment progress: {enroll_percentage:.1f}%", end="")

    print("\nVoice enrollment complete.")
    recorder.stop()
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
    name = input("enter the new user's name: ")

    existing_names = [user[1].lower() for user in userClass.getAllUsers()]
    if name.strip().lower() in existing_names:
        print(f"error: a user named '{name}' is already enrolled")
        return

    password = input("enter the new user's password: ")
    ff = getFaceEncoding()
    if not ff:
        print("error: face enrollment failed, user not added")
        return

    duplicate = isFaceAlreadyEnrolled(ff)
    if duplicate:
        print(f"error: this face is already enrolled under '{duplicate}'")
        return

    ap = getAudioEncoding(name)

    if ff and ap:
        if userClass.addUser(name, password, ff, ap):
            print(name + " added to users list")
        else:
            print("error: user was not added")
    else:
        print("error: face or voice enrollment failed\n")


def removeUser():
    showUsers()
    op = int(input("enter the user's id to remove: "))
    result = userClass.getOneUser(op)

    if result is None:
        print("no user found with this id")
        return

    id, name, password, ff, ap, isActive = result
    if userClass.deleteUser(op):
        print(f"user '{name}' removed")
    else:
        print("error: user was not deleted")


systemLoop = True
print("=== Attendance System — User Enrollment ===\n")
while systemLoop:

    print(f"1. show users ({getUserCount()})\n"
          "2. add a user\n"
          "3. modify a user\n"
          "4. remove a user\n"
          "5. exit\n")

    op = input("enter option number: ")

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
            print("system closed")
            break

        case _:
            print("\nInvalid option\n")


recorder.delete()
eagle_profiler.delete()
