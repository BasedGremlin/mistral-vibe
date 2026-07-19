' WORDLIB (D:) -- Double-Click Entry Point
' Runs RUN_ME.bat in a visible CMD window.
' Use this if you prefer VBS over BAT as your double-click file.
Set WshShell = CreateObject("WScript.Shell")
ScriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.Run "cmd.exe /k """ & ScriptDir & "RUN_ME.bat""", 1, False
