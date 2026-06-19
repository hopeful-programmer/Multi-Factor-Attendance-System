import os
import bcrypt
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


class User:

    def __init__(self):
        self.mydb = None

    def connect(self):
        self.mydb = mysql.connector.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            database=os.environ.get("DB_NAME", "attendance_db")
        )
        self.mycursor = self.mydb.cursor()

    def close(self):
        if self.mydb is not None:
            self.mycursor.close()
            self.mydb.close()

    def addUser(self, name, password, face_features, audio_profile):
        self.connect()
        noErr = True
        name = name.strip()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        sql = "INSERT INTO user_tbl (name, password, face_features, audio_profile) VALUES (%s, %s, %s, %s)"
        try:
            self.mycursor.execute(sql, (name, hashed_password, face_features, audio_profile))
        except Exception as e:
            print(e)
            noErr = False
        finally:
            self.mydb.commit()
            self.close()
            return noErr

    def updateUser(self, id, name=None, password=None, face_features=None, audio_profile=None, isActive=None):
        self.connect()
        self.mycursor.execute("SELECT * FROM user_tbl WHERE user_id = %s", (id,))
        result = self.mycursor.fetchone()
        if result is None:
            print("no user with this id is found")
            self.close()
            return False

        tmp_id, tmp_name, tmp_password, tmp_face_features, tmp_audio_profile, tmp_isActive = result

        if name is None:
            name = tmp_name
        if password is None:
            password = tmp_password
        else:
            password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        if face_features is None:
            face_features = tmp_face_features
        if audio_profile is None:
            audio_profile = tmp_audio_profile
        if isActive is None:
            isActive = tmp_isActive

        sql = "UPDATE user_tbl SET name = %s, password = %s, face_features = %s, audio_profile = %s, isActive = %s WHERE user_id = %s"
        self.mycursor.execute(sql, (name, password, face_features, audio_profile, isActive, id))
        self.mydb.commit()
        self.close()

    def deleteUser(self, id):
        self.connect()
        self.mycursor.execute("SELECT * FROM user_tbl WHERE user_id = %s AND isActive = 'True'", (id,))
        result = self.mycursor.fetchone()
        if result is None:
            print("no user with this id is found")
            self.close()
            return False

        self.mycursor.execute("UPDATE user_tbl SET isActive = 'False' WHERE user_id = %s", (id,))
        self.mydb.commit()
        self.close()
        return True

    def getOneUser(self, id):
        self.connect()
        self.mycursor.execute("SELECT * FROM user_tbl WHERE user_id = %s AND isActive = 'True'", (id,))
        result = self.mycursor.fetchone()
        self.close()
        return result

    def getAllUsers(self):
        self.connect()
        self.mycursor.execute("SELECT * FROM user_tbl WHERE isActive = 'True'")
        result = self.mycursor.fetchall()
        self.close()
        return result

    def markAttended(self, id=None, credential=(None, None)):
        if id is not None:
            self.connect()
            noErr = True
            try:
                self.mycursor.execute("INSERT INTO attendance_tbl VALUES (null, %s, null)", (id,))
            except mysql.connector.Error as e:
                if e.sqlstate == '23000':
                    print("no user with this user id")
                elif e.sqlstate == '45000':
                    print("attendance already recorded for today")
                noErr = False
            finally:
                self.mydb.commit()
                self.close()
            return noErr

        if credential != (None, None):
            name, password = credential
            self.connect()
            self.mycursor.execute(
                "SELECT user_id, password FROM user_tbl WHERE name = %s AND isActive = 'True'",
                (name,)
            )
            result = self.mycursor.fetchone()
            self.close()
            if result:
                user_id, stored_hash = result
                if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
                    noErr = self.markAttended(id=user_id)
                    print("attendance recorded via password fallback")
                    return noErr
                else:
                    print("invalid credentials")
                    return False
            else:
                print("no user found with provided name")
                return False

        return True
