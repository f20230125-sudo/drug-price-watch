# Opens the workbook in Excel, recalculates and saves it (so previews and other readers see values, not zeros).
param([string]$Path)
$ErrorActionPreference = 'Stop'
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false
try {
  $wb = $xl.Workbooks.Open($Path)
  $wb.Application.CalculateFull()
  $wb.Worksheets.Item('Inputs').Activate()
  $wb.Save(); $wb.Close($true); "recalculated and saved"
} finally { $xl.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) }
