import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

while True:
    print("\n=== Multi-Factor Attendance System ===")
    print("1. Start attendance monitor")
    print("2. User management (admin)")
    print("3. Exit")

    choice = input("\nEnter option: ").strip()

    if choice == '1':
        subprocess.run([sys.executable, 'monitor.py'])
    elif choice == '2':
        subprocess.run([sys.executable, 'enroll.py'])
    elif choice == '3':
        print("System terminated")
        break
    else:
        print("\nInvalid option\n")
