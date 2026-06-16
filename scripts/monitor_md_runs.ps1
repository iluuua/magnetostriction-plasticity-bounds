param(
    [int]$IntervalSec = 600,
    [int]$Tail = 80,
    [switch]$Watch,
    [switch]$SaveSnapshots
)

$ErrorActionPreference = "Continue"

$RunRoots = @(
    "runs\stageB_nearGB_vacancies_focus_100k\20260615-215533",
    "runs\stageB_realism_100k\20260613-222836"
) | Where-Object { Test-Path $_ }

function Section($name) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " $name"
    Write-Host "============================================================"
}

function Sub($name) {
    Write-Host ""
    Write-Host "=== $name ==="
}

function ActiveProcesses {
    Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and (
            $_.Name -like "lmp_kokkos_cuda*" -or
            ($_.Name -match "python" -and $_.CommandLine -like "*run_stage_sweep.py*") -or
            $_.CommandLine -like "*stageB_nearGB_vacancies_focus_100k*" -or
            $_.CommandLine -like "*stageB_realism_100k*" -or
            $_.CommandLine -like "*stageC_1M*"
        )
    } |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine
}

function PrintGpu {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit --format=csv,noheader,nounits
    } else {
        Write-Host "nvidia-smi not found"
    }
}

function PrintDisk {
    Get-PSDrive -PSProvider FileSystem |
    Select-Object Name, Root,
        @{Name="FreeGB";Expression={[math]::Round($_.Free/1GB,2)}},
        @{Name="UsedGB";Expression={[math]::Round($_.Used/1GB,2)}} |
    Format-Table -AutoSize
}

function PrintState($root) {
    $p = Join-Path $root "state.json"

    if (-not (Test-Path $p)) {
        Write-Host "NO state.json"
        return
    }

    try {
        $s = Get-Content -Raw -Encoding UTF8 $p | ConvertFrom-Json
        Write-Host "updated_at:" $s.updated_at

        $s.cases.PSObject.Properties |
        ForEach-Object {
            $c = $_.Value

            $steps = $c.steps
            if ($null -eq $steps) { $steps = $c.current_step }

            $target = $c.target_steps
            if ($null -eq $target) { $target = $c.target }

            $pct = ""
            if ($target -and $steps -ne $null) {
                $pct = "{0:N1}%" -f (100 * [double]$steps / [double]$target)
            }

            [PSCustomObject]@{
                case    = $_.Name
                phase   = $c.phase
                status  = $c.status
                success = $c.success
                steps   = $steps
                target  = $target
                pct     = $pct
                tps     = $c.tps
                exit    = $c.exit_code
            }
        } | Format-Table -AutoSize
    } catch {
        Write-Host "FAILED TO PARSE state.json"
        Write-Host $_
    }
}

function PrintCsv($path, $title) {
    Sub $title

    if (Test-Path $path) {
        try {
            Import-Csv $path | Format-Table -AutoSize
        } catch {
            Get-Content -Encoding UTF8 $path -Tail 80
        }
    } else {
        Write-Host "missing"
    }
}

function LatestLog($root) {
    Get-ChildItem $root -Recurse -File -Include "*.lammps","*.log","*.txt" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like "log*.lammps" -or
        $_.Name -like "*runner*stdout*.txt" -or
        $_.Name -like "*runner*stderr*.txt" -or
        $_.Name -like "stdout.chunk*.txt" -or
        $_.Name -like "stderr.chunk*.txt"
    } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
}

function LastStep($logPath) {
    if (-not (Test-Path $logPath)) { return $null }

    try {
        $text = Get-Content -Raw -Encoding UTF8 $logPath
        $matches = [regex]::Matches($text, "(?m)^\s*(\d+)\s+\d+\s+")
        if ($matches.Count -eq 0) { return $null }

        return ($matches | ForEach-Object { [int]$_.Groups[1].Value } | Sort-Object -Descending | Select-Object -First 1)
    } catch {
        return $null
    }
}

function PrintLogs($root) {
    Sub "Latest log files"

    Get-ChildItem $root -Recurse -File -Include "*.lammps","*.log","*.txt" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like "log*.lammps" -or
        $_.Name -like "*runner*stdout*.txt" -or
        $_.Name -like "*runner*stderr*.txt" -or
        $_.Name -like "stdout.chunk*.txt" -or
        $_.Name -like "stderr.chunk*.txt"
    } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 10 FullName, Length, LastWriteTime |
    Format-Table -AutoSize

    Sub "Latest log tail"

    $log = LatestLog $root
    if ($log) {
        Write-Host $log.FullName
        $step = LastStep $log.FullName
        if ($null -ne $step) {
            Write-Host "parsed_last_step: $step"
        }
        Get-Content -Encoding UTF8 $log.FullName -Tail $Tail
    } else {
        Write-Host "No log found"
    }
}

function PrintRestartsDumps($root) {
    Sub "Latest restarts"

    Get-ChildItem $root -Recurse -File -Filter "restart.*" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 12 FullName,
        @{Name="GB";Expression={[math]::Round($_.Length/1GB,3)}},
        LastWriteTime |
    Format-Table -AutoSize

    Sub "Latest dumps"

    Get-ChildItem $root -Recurse -File -Include "*.lammpstrj","dump.*" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*.lammpstrj" -or $_.Name -like "dump.*" } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 12 FullName,
        @{Name="GB";Expression={[math]::Round($_.Length/1GB,3)}},
        LastWriteTime |
    Format-Table -AutoSize
}

function PrintAnalysis($root) {
    Sub "Analysis / DXA"

    $files = Get-ChildItem $root -Recurse -File -Filter "analysis.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "handoff_completed_cases_snapshot" } |
    Sort-Object LastWriteTime -Descending

    if (-not $files) {
        Write-Host "No analysis.json found"
        return
    }

    foreach ($f in $files) {
        Write-Host ""
        Write-Host "--- $($f.FullName) ---"

        try {
            $a = Get-Content -Raw -Encoding UTF8 $f.FullName | ConvertFrom-Json
            [PSCustomObject]@{
                dislocation_segments       = $a.dislocation_segments
                dislocation_length_A       = $a.dislocation_length_A
                dislocation_density_per_m2 = $a.dislocation_density_per_m2
                hcp_atoms                  = $a.hcp_atoms
                other_atoms                = $a.other_atoms
                hcp_beyond_1p3_shell       = $a.plastic_zone.hcp_atoms_beyond_1p3_shell
                defect_beyond_1p3_shell    = $a.plastic_zone.defect_atoms_beyond_1p3_shell
                max_displacement           = $a.max_displacement
            } | Format-List
        } catch {
            Write-Host "failed to parse analysis.json"
        }
    }
}

function PrintErrors($root) {
    Sub "Error scan"

    $hits = Get-ChildItem $root -Recurse -File -Include "*.log","*.txt","*.lammps","*.md","*.json" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "status_dump_|monitor_snapshots" } |
    Select-String -Pattern "ERROR|Error|error|Lost atoms|nan|NaN|CUDA|cudaError|exception|Traceback|failed|FAILED|STOPPED|timeout|hang|Cannot open" |
    Select-Object -First 60 Path, LineNumber, Line

    if ($hits) {
        $hits | Format-Table -AutoSize
    } else {
        Write-Host "No error patterns found"
    }
}

function PrintReports($root) {
    Sub "Reports"

    $names = @(
        "final_report.md",
        "hang_recovery_report.md",
        "focused_failure_diagnosis.md",
        "focused_recovery_launch_record.md",
        "event_pipeline_initial_dry_run_report.md",
        "event_pipeline_recovery_dry_run_report.md",
        "focus_run_preflight.md"
    )

    foreach ($name in $names) {
        $p = Join-Path $root $name
        if (Test-Path $p) {
            Write-Host ""
            Write-Host "--- $p ---"
            Get-Content -Encoding UTF8 $p -Tail 80
        }
    }
}

function PrintRun($root) {
    Section "RUN ROOT: $root"

    if (-not (Test-Path $root)) {
        Write-Host "MISSING"
        return
    }

    Sub "Root files"
    Get-ChildItem $root -Force -ErrorAction SilentlyContinue |
    Select-Object Name, Length, LastWriteTime |
    Format-Table -AutoSize

    Sub "State"
    PrintState $root

    PrintCsv (Join-Path $root "smoke_summary.csv") "smoke_summary.csv"
    PrintCsv (Join-Path $root "production_summary.csv") "production_summary.csv"
    PrintCsv (Join-Path $root "defect_summary.csv") "defect_summary.csv"
    PrintCsv (Join-Path $root "runtime_summary.csv") "runtime_summary.csv"

    PrintLogs $root
    PrintRestartsDumps $root
    PrintAnalysis $root
    PrintReports $root
    PrintErrors $root
}

function Snapshot {
    Section "MD MONITOR | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    Sub "Active MD processes"
    $p = ActiveProcesses
    if ($p) { $p | Format-List } else { Write-Host "No active MD processes found" }

    Sub "GPU"
    PrintGpu

    Sub "Disk"
    PrintDisk

    foreach ($root in $RunRoots) {
        PrintRun $root
    }

    Section "END MONITOR"
}

if (-not $RunRoots -or $RunRoots.Count -eq 0) {
    Write-Host "No run roots found"
    exit 1
}

do {
    if ($SaveSnapshots) {
        New-Item -ItemType Directory -Force -Path "monitor_snapshots" | Out-Null
        $path = "monitor_snapshots\md_monitor_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
        Snapshot 2>&1 | Tee-Object -FilePath $path
        Write-Host "Saved snapshot: $path"
    } else {
        Snapshot
    }

    if ($Watch) {
        Write-Host ""
        Write-Host "Sleeping $IntervalSec seconds. Press Ctrl+C to stop."
        Start-Sleep -Seconds $IntervalSec
    }
} while ($Watch)
