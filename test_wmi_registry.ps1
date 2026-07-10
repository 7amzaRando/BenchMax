# Test 1: WMI Win32_VideoController
$wmi = Get-WmiObject -Class Win32_VideoController -ErrorAction SilentlyContinue
if ($wmi) {
    Write-Host "=== WMI Win32_VideoController ==="
    Write-Host "Name: $($wmi.Name)"
    Write-Host "AdapterRAM (bytes): $($wmi.AdapterRAM)"
}

# Test 2: Registry VRAM for each GPU
Write-Host "`n=== Registry HardwareInformation.qwMemorySize ===" -ForegroundColor Cyan
$base_path = "SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
try {
    $subkeys = Get-ChildItem -Path $base_path -ErrorAction SilentlyContinue
    foreach ($key in $subkeys) {
        try {
            $driver_desc = $key.GetValue("DriverDesc")
            if ($driver_desc) {
                Write-Host "Driver: $($driver_desc)" -ForegroundColor Yellow
                $vram = $key.GetValue("HardwareInformation.qwMemorySize")
                if ($vram -ne $null) {
                    Write-Host "  VRAM (bytes): $vram" 
                    Write-Host "  VRAM (MB): $([math]::Round($vram / (1024 * 1024), 0))"
                } else {
                    Write-Host "  HardwareInformation.qwMemorySize: NOT FOUND" -ForegroundColor Red
                }
            }
        } catch {
            Write-Host "Error reading key: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
} catch {
    Write-Host "WMI/Registry error: $($_.Exception.Message)" -ForegroundColor Red
}
