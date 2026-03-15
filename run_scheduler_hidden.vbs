' CasehugBot Scheduler - INVISIBLE RUN (no console)
' This VBS script completely hides the console

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get current script directory
strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Build path to Python and scheduler.py
strPythonPath = strScriptPath & "\.venv\Scripts\pythonw.exe"
strSchedulerPath = strScriptPath & "\scheduler.py"

' Check if pythonw.exe exists in venv
If objFSO.FileExists(strPythonPath) Then
    ' Run with pythonw from venv
    strCommand = """" & strPythonPath & """ """ & strSchedulerPath & """"
Else
    ' Fallback: use system pythonw
    strCommand = "pythonw """ & strSchedulerPath & """"
End If

' Run COMPLETELY HIDDEN (0 = invisible window, False = don't wait for completion)
objShell.Run strCommand, 0, False

' 0 = SW_HIDE (completely hidden, no console, nothing)
' False = don't wait for completion (allows scheduler to run in background)
