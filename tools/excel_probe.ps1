param([string]$Path, [string]$ScenarioFile, [string]$Out)
# Drives Excel itself through the input scenarios in excel/probe_scenarios.json and writes what Excel's formulas
# returned, so tools/verify_workbook.py can compare them with an independent Python calculation.
$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Path)
  $inp = $wb.Worksheets.Item('Inputs'); $tr = $wb.Worksheets.Item('Tracker')
  $sc = $wb.Worksheets.Item('Entry scenario'); $ck = $wb.Worksheets.Item('Checks')
  # Windows PowerShell 5.1 hands back a JSON array as one object; the pipeline unrolls it.
  $scenarios = @(Get-Content -Raw -Path $ScenarioFile | ConvertFrom-Json | ForEach-Object { $_ })
  $result = @()
  foreach ($s in $scenarios) {
    $inp.Range('C4').Value2 = [string]$s.product
    $inp.Range('C5').Value2 = [string]$s.compare
    $inp.Range('C6').Value2 = [double]$s.base
    $inp.Range('C7').Value2 = [double]$s.end
    $inp.Range('C10').Value2 = [double]$s.keep4
    $inp.Range('C11').Value2 = [double]$s.keep8
    $inp.Range('C12').Value2 = [double]$s.move4
    $inp.Range('C13').Value2 = [double]$s.move8
    $wb.Application.CalculateFull()
    $single = @{}
    foreach ($a in 'B4','B5','B6','B7','B8','B9','B11','B12','B13','B14','B16','B17','B19','B20','B21','B22','B23') { $single[$a] = $tr.Range($a).Value2 }
    $years = @()
    $v = $tr.Range('A26:E39').Value2
    for ($i = 1; $i -le 14; $i++) { $r = @(); for ($c = 1; $c -le 5; $c++) { $r += ,$v[$i, $c] }; $years += ,$r }
    $scen = @{}
    foreach ($a in 'B4','B5','B6') { $scen[$a] = $sc.Range($a).Value2 }
    $sv = $sc.Range('B9:E11').Value2
    $table = @(); for ($i = 1; $i -le 3; $i++) { $r = @(); for ($c = 1; $c -le 4; $c++) { $r += ,$sv[$i, $c] }; $table += ,$r }
    $checks = @(); foreach ($r in 5..10) { $checks += [string]$ck.Cells.Item($r, 5).Value2 }
    $result += [pscustomobject]@{ id = $s.id; inputs = $s; tracker = $single; years = $years; scenario = $scen; table = $table;
                                  checks = $checks; overall = [string]$ck.Range('E12').Value2; row = $inp.Range('C15').Value2 }
  }
  $result | ConvertTo-Json -Depth 7 -Compress | Set-Content -Path $Out -Encoding UTF8
  $wb.Close($false)
  "ok"
} finally { $xl.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
