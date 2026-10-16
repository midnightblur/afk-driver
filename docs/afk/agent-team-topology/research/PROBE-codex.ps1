$ErrorActionPreference = 'Stop'
$probeRoot = $PSScriptRoot
$probeInfo = [System.Diagnostics.ProcessStartInfo]::new()
$probeInfo.FileName = 'C:\Program Files\1DevTool\1DevTool.exe'
$probeInfo.WorkingDirectory = $probeRoot
$probeInfo.UseShellExecute = $false
$probeInfo.CreateNoWindow = $true
$probeInfo.RedirectStandardInput = $true
$probeInfo.RedirectStandardOutput = $true
$probeInfo.RedirectStandardError = $true
$probeInfo.Environment['ELECTRON_RUN_AS_NODE'] = '1'
foreach ($arg in @('C:\Program Files\1DevTool\resources\app.asar.unpacked\dist\cli\1devtool-agent.cjs','run','--to=codex','--prompt-stdin','--timeout=5','--no-link','--model=gpt-5.6-sol','--json')) {
    $probeInfo.ArgumentList.Add($arg)
}
$probeProcess = [System.Diagnostics.Process]::new()
$probeProcess.StartInfo = $probeInfo
$probeChildren = @{}
$probeClock = [System.Diagnostics.Stopwatch]::StartNew()
try {
    [void]$probeProcess.Start()
    $probeChildren[$probeProcess.Id] = $probeProcess
    $probeOut = $probeProcess.StandardOutput.ReadToEndAsync()
    $probeErr = $probeProcess.StandardError.ReadToEndAsync()
    $probeProcess.StandardInput.WriteLine('Bounded transport probe. Do not use tools. Reply with exactly PROBE_OK.')
    $probeProcess.StandardInput.Close()
    while (-not $probeProcess.HasExited -and $probeClock.Elapsed.TotalSeconds -lt 20) {
        foreach ($row in (Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name)) {
            if ($probeChildren.ContainsKey([int]$row.ParentProcessId) -and -not $probeChildren.ContainsKey([int]$row.ProcessId)) {
                try {
                    $probeChildren[[int]$row.ProcessId] = [System.Diagnostics.Process]::GetProcessById([int]$row.ProcessId)
                } catch { }
            }
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $probeProcess.HasExited) { $probeProcess.Kill($true) }
    [void]$probeProcess.WaitForExit(5000)
    $probeRecords = foreach ($entry in $probeChildren.GetEnumerator()) {
        $process = $entry.Value
        $name = try { $process.ProcessName } catch { 'exited' }
        $wasAlive = -not $process.HasExited
        if ($wasAlive) { $process.Kill($true); [void]$process.WaitForExit(5000) }
        [ordered]@{ pid=$entry.Key; name=$name; requiredCleanup=$wasAlive; exited=$process.HasExited }
    }
    [ordered]@{
        observedAt=[DateTime]::UtcNow.ToString('o'); command='1devtool-agent run --to=codex --prompt-stdin --timeout=5 --no-link --model=gpt-5.6-sol --json';
        rootPid=$probeProcess.Id; elapsedSeconds=[Math]::Round($probeClock.Elapsed.TotalSeconds,2); exitCode=$probeProcess.ExitCode;
        processes=@($probeRecords); stdout=$probeOut.GetAwaiter().GetResult(); stderr=$probeErr.GetAwaiter().GetResult()
    } | ConvertTo-Json -Depth 8 | Tee-Object -FilePath (Join-Path $probeRoot 'EVIDENCE-codex-live.json')
} finally {
    foreach ($process in $probeChildren.Values) {
        if (-not $process.HasExited) { $process.Kill($true); [void]$process.WaitForExit(5000) }
    }
}
