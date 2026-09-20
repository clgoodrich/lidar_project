<#
Mirror this repo to BOTH external disks in one pass.

WHY A THIRD SCRIPT
------------------
    tools/backup_to_E.bat    letter-keyed, SUPERSEDED, kept for provenance
    tools/backup_to_t7.ps1   label-keyed, ONE disk (the T7), retries on dropout
    tools/backup_to_externals.ps1   <- this one: label-keyed, BOTH disks

The T7 and the Seagate both hold a full mirror at the same relative path, and
keeping them in step meant running two different scripts by hand. This does both
in sequence, resolving each BY VOLUME LABEL.

The label matters and is not paranoia. On 2026-09-03 the T7 was mounted as F:,
dropped off the USB bus mid-copy and came back as E:; a Seagate held E: in
between. On 2026-09-19 the T7 was E: and the Seagate F:, and the T7 then
disappeared from the bus entirely mid-session. A launcher hardcoded to a letter
will write 91 GB onto whichever disk answers to it.

COPY POLICY -- unchanged from the other two scripts
---------------------------------------------------
robocopy /E /XO compares timestamp + size per file:
    new file          -> copied
    source is newer   -> copied
    identical         -> skipped
    target is newer   -> skipped (/XO)
Nothing is ever deleted from a backup. /MIR is deliberately NOT used. This is
why the mirrors (161 GB, 174 GB) exceed the 91 GB repo: they retain the
pre-reorganisation layout as a rollback point. That is the intent, not waste.

EXIT CODES
----------
    0   every attached target copied cleanly
    8+  a target was attached and robocopy reported failures
    4   a target was NOT attached and was skipped

Skipping an absent disk is NOT a failure. The first version of this returned 16
for it, which read as fatal in the task log when the copy that did run was
clean. An absent disk now exits 4 and says which one.

  powershell -ExecutionPolicy Bypass -File tools/backup_to_externals.ps1
  ... -Only T7
  ... -ExcludeInFlight 'data\9t\derived\smrf05'
#>
param(
    [string[]] $Only = @(),
    [string[]] $ExcludeInFlight = @()
)

$ErrorActionPreference = 'Stop'
$src = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'

$targets = @(
    @{ Label = 'T7';                     Sub = 'Colton\_BACKUPS\lidar_project_MIRROR' },
    @{ Label = 'Seagate Portable Drive'; Sub = 'Colton\_BACKUPS\lidar_project_MIRROR' }
)
if ($Only.Count) { $targets = $targets | Where-Object { $Only -contains $_.Label } }

$skipped = @()
$failed  = @()
$ok      = @()

foreach ($t in $targets) {
    $v = Get-Volume -ErrorAction SilentlyContinue |
         Where-Object { $_.FileSystemLabel -eq $t.Label -and $_.DriveLetter }
    if (-not $v) {
        Write-Host "[SKIP] no mounted volume labelled '$($t.Label)' - not attached"
        $skipped += $t.Label
        continue
    }
    if ($v.Count -gt 1) {
        Write-Host "[SKIP] more than one volume labelled '$($t.Label)' - refusing to guess"
        $failed += $t.Label
        continue
    }

    $dst = Join-Path ("$($v.DriveLetter):\") $t.Sub
    $log = Join-Path $env:TEMP "backup_$($v.DriveLetter)_$stamp.log"
    Write-Host ""
    Write-Host "=== $($t.Label)  ($($v.DriveLetter):)  ->  $dst"
    Write-Host "    log $log"
    New-Item -ItemType Directory -Force $dst | Out-Null

    # Two traps here, both of which produced a silent robocopy 16:
    #   $args is a PowerShell AUTOMATIC variable; assigning to it mangles the
    #     argument list and robocopy never runs. Hence $rcArgs.
    #   '/LOG:' + $log inside an array literal is split into TWO elements, so
    #     robocopy receives a bare /LOG: with no path and aborts. It has to be a
    #     single interpolated string, "/LOG:$log".
    $rcArgs = @($src, $dst, '/E', '/XO', '/XJ', '/FFT', '/R:1', '/W:3', '/MT:8',
              '/NP', '/NDL', "/LOG:$log")
    foreach ($x in $ExcludeInFlight) { $rcArgs += @('/XD', (Join-Path $src $x)) }
    robocopy @rcArgs | Out-Null
    $rc = $LASTEXITCODE

    Get-Content $log -Tail 12 -ErrorAction SilentlyContinue | Where-Object { $_ -match '\S' } |
        ForEach-Object { Write-Host "    $_" }

    # robocopy bit flags: 1 copied, 2 extras, 4 mismatched, 8 failed, 16 fatal.
    if ($rc -lt 8) {
        Write-Host "    [OK] robocopy $rc"
        $ok += $t.Label
        Add-Content "$dst\_BACKUP_MANIFEST.txt" -Encoding utf8 -Value (
            "run {0}  label {1}  drive {2}:  robocopy {3}{4}" -f `
            (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $t.Label, $v.DriveLetter, $rc,
            $(if ($ExcludeInFlight.Count) { "  (excluded: $($ExcludeInFlight -join ', '))" } else { "" }))
    } else {
        Write-Host "    [FAIL] robocopy $rc - files failed; see the log"
        $failed += $t.Label
    }
}

Write-Host ""
Write-Host ("copied : " + $(if ($ok.Count)      { $ok -join ', ' }      else { 'none' }))
Write-Host ("skipped: " + $(if ($skipped.Count) { $skipped -join ', ' } else { 'none' }))
Write-Host ("failed : " + $(if ($failed.Count)  { $failed -join ', ' }  else { 'none' }))

if ($failed.Count)  { exit 8 }
if ($skipped.Count) { exit 4 }
exit 0
