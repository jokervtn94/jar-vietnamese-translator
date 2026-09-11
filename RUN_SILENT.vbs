Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
shell.Run Chr(34) & base & "\RUN_JAR_TRANSLATOR.bat" & Chr(34), 0, False
