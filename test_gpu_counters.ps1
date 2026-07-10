$err=@{}
$util = Get-Counter '\GPU Engine(*)\Utilization Percentage' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue
if ($util) {
    $sum = ($util.CounterSamples | Measure-Object -Maximum CookedValue).Maximum
    $err['load'] = [math]::Round($sum, 1)
}
$mem = Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage' -SampleInterval 1 -MaxSamples 1 -ErrorAction SilentlyContinue
if ($mem) {
    $samples = $mem.CounterSamples | Where-Object { $_.CookedValue -gt 0 }
    $used = ($samples | Measure-Object -Maximum CookedValue).Maximum
    if ($used -and $used -gt 0) {
        $err['vram_used_mb'] = [math]::Round($used / 1MB, 0)
    }
}
ConvertTo-Json -InputObject $err -Compress
