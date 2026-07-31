param(
  [Parameter(Mandatory = $true)][ValidateSet("probe", "read", "write")][string]$Action,
  [string]$Source,
  [string]$Destination
)

$ErrorActionPreference = "Stop"
$app = New-Object -ComObject Statistica.Application
try {
  try { $app.Visible = $false } catch {}
  if ($Action -eq "probe") {
    Write-Output "ok"
    exit 0
  }
  $document = $app.Documents.Open($Source)
  $document.SaveAs($Destination, $true)
  try { $document.Close() } catch {}
} finally {
  try { $app.Quit() } catch {}
}
