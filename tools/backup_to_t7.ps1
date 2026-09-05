<#
Back up this repo to the Samsung PSSD T7, incrementally and repeatably.

WHY THIS IS NOT A .BAT WITH A DRIVE LETTER
------------------------------------------
On 2026-09-03 the T7 was mounted as F:, dropped off the USB bus mid-copy, and
came back as E:. A second disk (a Seagate Portable) briefly held E: in between.
A launcher hardcoded to a letter will happily write 143 GB onto whichever disk
happens to answer to that letter. This script resolves the target by VOLUME
LABEL and re-resolves it before every pass, so it either finds the right disk
or refuses.

COPY POLICY (same as tools/backup_to_E.bat)
-------------------------------------------
robocopy /E /XO compares timestamp + size per file:
    new file          -> copied
    source is newer   -> copied
    identical         -> skipped
    target is newer   -> skipped (/XO)
Nothing is ever deleted from the backup. /MIR is deliberately NOT used.

Because every pass is incremental, an interrupted run costs only the files it
had not reached yet. That is why this retries: the T7 has been dropping under
sustained write load, and repeated cheap passes are the way to converge.

Exit 0 only when a pass completes with zero failures.

  powershell -ExecutionPolicy Bypass -File tools/backup_to_t7.ps1
  ... -Label T7 -SubPath 'lidar_project_data_DO_NOT_DELETE\lidar_project_repo_MIRROR'
  ... -MaxPasses 8
#>
param(
    [string]$Label     = 'T7',
    [string]$SubPath   = 'lidar_project_data_DO_NOT_DELETE\lidar_project_repo_MIRROR',
    [int]   $MaxPasses = 6,
    [int]   $WaitSec   = 20
)

$ErrorActionPreference = 'Stop'
$src = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$log = Join-Path $src 'backup_to_t7_last_run.log'

function Resolve-Target {
    # Re-resolved before EVERY pass. The letter is not stable; the label is.
    $v = Get-Volume -ErrorAction SilentlyContinue |
         Where-Object { $_.FileSystemLabel -eq $Label -and $_.DriveLetter }
    if (-not $v)          { return $null }
    if ($v.Count -gt 1)   { throw "more than one volume is labelled '$Label' - refusing to guess" }
    return (Join-Path ("$($v.DriveLetter):\") $SubPath)
}

for ($pass = 1; $pass -le $MaxPasses; $pass++) {
    $dst = Resolve-Target
    if (-not $dst) {
        Write-Host "[pass $pass] no mounted volume labelled '$Label'. Waiting ${WaitSec}s ..."
        Start-Sleep -Seconds $WaitSec
        continue
    }

    Write-Host "[pass $pass] $src  ->  $dst"
    New-Item -ItemType Directory -Force $dst | Out-Null
    robocopy $src $dst /E /XO /XJ /FFT /R:1 /W:3 /MT:8 /NP /NDL /LOG+:"$log" | Out-Null
    $rc = $LASTEXITCODE

    # robocopy bit flags: 1 copied, 2 extras, 4 mismatched, 8 failed, 16 fatal.
    if ($rc -lt 8) {
        Write-Host "[pass $pass] clean (robocopy $rc). Backup is complete."
        if (Test-Path $dst) {
            Add-Content "$dst\_BACKUP_MANIFEST.txt" -Encoding utf8 `
                -Value ("run {0}  pass {1}  robocopy {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $pass, $rc)
        }
        exit 0
    }

    Write-Host "[pass $pass] robocopy $rc - files failed. The T7 most likely dropped off the bus."
    Start-Sleep -Seconds $WaitSec
}

Write-Host "Gave up after $MaxPasses passes. The backup is INCOMPLETE."
Write-Host "This is a connection fault, not a repo problem - reseat the T7 in a"
Write-Host "rear motherboard USB port (no hub) and run this again; it resumes."
exit 1
