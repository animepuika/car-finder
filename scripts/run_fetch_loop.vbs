Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "C:\Users\krist\Desktop\car-finder"
objShell.Run """C:\Users\krist\Desktop\car-finder\.venv\Scripts\python.exe"" manage.py run_fetch_loop", 0, False
