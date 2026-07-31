param(
  [Parameter(Mandatory = $true)][ValidateSet("probe", "read", "write")][string]$Action,
  [string]$Source,
  [string]$Destination
)

$ErrorActionPreference = "Stop"
$app = New-Object -ComObject Mtb.Application
try {
  $app.UserInterface.Visible = $false
  if ($Action -eq "probe") {
    Write-Output "ok"
    exit 0
  }

  $project = $app.ActiveProject
  if ($Action -eq "read") {
    $extension = [IO.Path]::GetExtension($Source).ToLowerInvariant()
    if ($extension -eq ".mpx" -or $extension -eq ".mpj") {
      $app.Open($Source)
      $project = $app.ActiveProject
    } else {
      $project.Worksheets.Open($Source)
    }
    $sheet = $project.ActiveWorksheet
    $command = 'WSAVE "' + $Destination.Replace('"', '""') + '"; FTYPE; XLSX.'
    $project.ExecuteCommand($command, $sheet)
  } else {
    $command = 'WOPEN "' + $Source.Replace('"', '""') + '"; FTYPE; XLSX.'
    $project.ExecuteCommand($command)
    $sheet = $project.ActiveWorksheet
    $extension = [IO.Path]::GetExtension($Destination).ToLowerInvariant()
    if ($extension -eq ".mpx" -or $extension -eq ".mpj") {
      $project.SaveAs($Destination, $false)
    } else {
      $sheet.SaveAs($Destination, $false)
    }
  }
} finally {
  try { $app.Quit() } catch {}
}
