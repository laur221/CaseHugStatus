' CasehugBot Scheduler - Rulare INVIZIBILA (fara consola)
' Acest script VBS ascunde complet consola

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Obtine directorul curent al scriptului
strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Construieste calea catre Python si scheduler.py
strPythonPath = strScriptPath & "\.venv\Scripts\pythonw.exe"
strSchedulerPath = strScriptPath & "\scheduler.py"

' Verifica daca pythonw.exe exista in venv
If objFSO.FileExists(strPythonPath) Then
    ' Ruleaza cu pythonw din venv
    strCommand = """" & strPythonPath & """ """ & strSchedulerPath & """"
Else
    ' Fallback: foloseste pythonw din sistem
    strCommand = "pythonw """ & strSchedulerPath & """"
End If

' Ruleaza COMPLET ASCUNS (0 = fereastra invizibila, False = asteapta terminare)
objShell.Run strCommand, 0, False

' 0 = SW_HIDE (complet ascuns, fara consola, fara nimic)
' False = nu astepta terminare (permite scheduler sa ruleze in background)
