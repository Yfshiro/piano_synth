用于将midi文件快速生成符合该项目要求的乐谱

假设 MIDI 文件位于项目目录 D:\code\python\midi，在 PowerShell 中执行：
```powershell
& C:\Users\LENOVO\.conda\envs\music\python.exe `
  D:\code\python\midi\midi_read.py `
  "D:\code\python\midi\千本樱.mid" `
  -o "D:\code\python\piano_synth\examples\千本樱.yaml"
```
简化单行命令：
```powershell
python .\midi\midi_read.py ".\midi\千本樱.mid" -o ".\examples\千本樱.yaml"
```
如果文件不在当前目录，将 MIDI 文件实际路径替换进去。可以先查看当前目录下的 MIDI 文件名：
```powershell
Get-ChildItem -File *.mid, *.midi
```
