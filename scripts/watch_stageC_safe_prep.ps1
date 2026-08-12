param(
    [string]$RunRoot = "runs\stageC_1M_nearGB_vacancies_eps0100_safe_prep\20260617-063915",
    [int]$IntervalSec = 120,
    [int]$TailLines = 40,
    [double]$MaxSafeTempK = 1000.0,
    [double]$MaxJumpRatio = 10.0,
    [double]$MinFreeDiskGB = 5.0
)

$ErrorActionPreference = "Continue"

function Section($Title) {
    Write-Host ""
    Write-Host ("=" * 100)
    Write-Host $Title
    Write-Host ("=" * 100)
}

function Get-FreeCGB {
    $drive = Get-PSDrive -Name C -ErrorAction SilentlyContinue
    if ($null -eq $drive) {
        return $null
    }
    return [math]::Round($drive.Free / 1GB, 2)
}

function Get-GpuLine {
    try {
        return nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader 2>$null
    } catch {
        return "nvidia-smi unavailable"
    }
}

function Get-LogPath($FullRunRoot) {
    $direct = Join-Path $FullRunRoot "cases\C1_1M_scaleup_100k\C1_1M_nearGB_vacancies_medium_eps0100\prep\log.C1_1M_nearGB_vacancies_medium_eps0100_prep.lammps"
    if (Test-Path $direct) {
        return $direct
    }

    $logs = Get-ChildItem $FullRunRoot -Recurse -File -Filter "log*.lammps" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending

    if ($logs.Count -gt 0) {
        return $logs[0].FullName
    }

    return $null
}

function Get-ThermoRows($LogPath) {
    $rows = @()

    if (!(Test-Path $LogPath)) {
        return $rows
    }

    $lines = Get-Content -Encoding UTF8 -Path $LogPath -ErrorAction SilentlyContinue

    foreach ($line in $lines) {
        $text = $line.Trim()

        if ($text -match "^\s*(\d+)\s+(\d+)\s+([-+0-9.Ee]+)") {
            $step = [int]$matches[1]
            $atoms = [int]$matches[2]
            $temp = [double]::Parse($matches[3], [System.Globalization.CultureInfo]::InvariantCulture)

            $rows += [PSCustomObject]@{
                Step  = $step
                Atoms = $atoms
                TempK = $temp
                Raw   = $line
            }
        }
    }

    return $rows
}

function Get-TempWarnings($Rows, $MaxSafeTempK, $MaxJumpRatio) {
    $warnings = @()

    if ($Rows.Count -eq 0) {
        return $warnings
    }

    $maxTemp = -1.0
    $maxStep = 0

    foreach ($row in $Rows) {
        if ($row.TempK -gt $maxTemp) {
            $maxTemp = $row.TempK
            $maxStep = $row.Step
        }
    }

    if ($maxTemp -gt $MaxSafeTempK) {
        $warnings += "TEMP_RUNAWAY: max Temp $maxTemp K at step $maxStep"
    }

    for ($i = 1; $i -lt $Rows.Count; $i++) {
        $prev = $Rows[$i - 1]
        $cur = $Rows[$i]

        if ($prev.TempK -gt 0 -and $cur.TempK -ge ($MaxJumpRatio * $prev.TempK)) {
            $warnings += "TEMP_JUMP: $($prev.TempK) K -> $($cur.TempK) K between steps $($prev.Step) and $($cur.Step)"
            break
        }
    }

    return $warnings
}

function Has-ErrorMarkers($LogPath) {
    if (!(Test-Path $LogPath)) {
        return $false
    }

    $patterns = @(
        "ERROR",
        "FATAL",
        "Lost atoms",
        "NaN",
        "cudaError",
        "out of memory",
        "Out of memory",
        "MPI_ABORT"
    )

    foreach ($pattern in $patterns) {
        $hit = Select-String -Path $LogPath -Pattern $pattern -SimpleMatch -Quiet -ErrorAction SilentlyContinue
        if ($hit) {
            return $true
        }
    }

    return $false
}

$ProjectRoot = (Get-Location).Path
$FullRunRoot = Join-Path $ProjectRoot $RunRoot

if (!(Test-Path $FullRunRoot)) {
    Write-Host "FATAL: RunRoot not found:"
    Write-Host $FullRunRoot
    exit 2
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$diagDir = Join-Path $ProjectRoot "diagnostics"
New-Item -ItemType Directory -Force -Path $diagDir | Out-Null

$csvPath = Join-Path $diagDir "watch_stageC_safe_prep_$stamp.csv"
"timestamp,status,step,tempK,freeCGB,gpu,lammpsActive,warnings" | Set-Content -Encoding UTF8 -Path $csvPath

Section "WATCH START"
Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "RunRoot:     $FullRunRoot"
Write-Host "CSV:         $csvPath"
Write-Host "Interval:    $IntervalSec sec"

while ($true) {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logPath = Get-LogPath $FullRunRoot
    $freeC = Get-FreeCGB
    $gpu = Get-GpuLine
    $lammps = Get-Process -Name "lmp_kokkos_cuda" -ErrorAction SilentlyContinue

    $rows = @()
    if ($null -ne $logPath) {
        $rows = @(Get-ThermoRows $logPath)
    }

    $lastStep = ""
    $lastTemp = ""
    $lastAtoms = ""

    if ($rows.Count -gt 0) {
        $last = $rows[$rows.Count - 1]
        $lastStep = $last.Step
        $lastTemp = $last.TempK
        $lastAtoms = $last.Atoms
    }

    $warnings = @(Get-TempWarnings $rows $MaxSafeTempK $MaxJumpRatio)

    if ($null -ne $freeC -and $freeC -lt $MinFreeDiskGB) {
        $warnings += "LOW_DISK: C free $freeC GB < $MinFreeDiskGB GB"
    }

    if ($null -ne $logPath -and (Has-ErrorMarkers $logPath)) {
        $warnings += "ERROR_MARKER_FOUND_IN_LOG"
    }

    $status = "RUNNING"

    if ($null -eq $lammps) {
        $status = "NO_ACTIVE_LAMMPS"
    }

    if ($warnings.Count -gt 0) {
        $status = "WARNING"
    }

    Clear-Host
    Section "STAGE C SAFE-PREP WATCH $now"

    Write-Host "Status:       $status"
    Write-Host "RunRoot:      $RunRoot"
    Write-Host "Log:          $logPath"
    Write-Host "C free:       $freeC GB"
    Write-Host "GPU:          $gpu"

    if ($null -eq $lammps) {
        Write-Host "LAMMPS:       not active"
    } else {
        Write-Host "LAMMPS PID:   $($lammps.Id)"
    }

    Write-Host ""
    Write-Host "Progress:"
    Write-Host "Step:         $lastStep"
    Write-Host "Atoms:        $lastAtoms"
    Write-Host "Temp K:       $lastTemp"

    Write-Host ""
    Write-Host "Warnings:"
    if ($warnings.Count -eq 0) {
        Write-Host "none"
    } else {
        foreach ($warning in $warnings) {
            Write-Host $warning
        }
    }

    if ($null -ne $logPath -and (Test-Path $logPath)) {
        Write-Host ""
        Write-Host "Last thermo rows:"
        if ($rows.Count -gt 0) {
            $start = [math]::Max(0, $rows.Count - 8)
            for ($i = $start; $i -lt $rows.Count; $i++) {
                Write-Host $rows[$i].Raw
            }
        }

        Write-Host ""
        Write-Host "Raw log tail:"
        Get-Content -Encoding UTF8 -Tail $TailLines $logPath
    }

    $gpuCsv = ($gpu -join " | ").Replace('"', "'")
    $warnCsv = ($warnings -join " | ").Replace('"', "'")
    $activeCsv = "yes"
    if ($null -eq $lammps) {
        $activeCsv = "no"
    }

    $csvLine = '"' + $now + '","' + $status + '","' + $lastStep + '","' + $lastTemp + '","' + $freeC + '","' + $gpuCsv + '","' + $activeCsv + '","' + $warnCsv + '"'
    Add-Content -Encoding UTF8 -Path $csvPath -Value $csvLine

    if ($status -eq "WARNING") {
        Write-Host ""
        Write-Host "ATTENTION: warning detected. Do NOT launch production."
    }

    if ($status -eq "NO_ACTIVE_LAMMPS") {
        Write-Host ""
        Write-Host "LAMMPS is not active. Inspect safe_prep_result.json, state.json, final_report.md."
        break
    }

    Start-Sleep -Seconds $IntervalSec
}
