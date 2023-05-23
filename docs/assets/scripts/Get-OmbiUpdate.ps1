# --------------------------------------------------------
# Script: Get-OmbiUpdate.ps1
# Author: Dyson Parkes, Berserkir-Net
# Contributors: Ryder, RyderTech
# Date: 22/10/2021 11:50:00
# Keywords: Media Tools, Update Scripts, Ombi
# Comments: 
# --------------------------------------------------------
# .\Get-OmbiUpdate.ps1 -APIKey YOURAPIKEY -OmbiURL https://ombi.example.com

#region Parameters (APIKey, OmbiDir, OmbiURL, UpdaterPath, ServiceName, Filename)
param(
# The API key to be used when requesting current details from your Ombi installation
[Parameter(Mandatory=$true, HelpMessage="Your Ombi API Key")][string]$APIKey,
# The folder Ombi is running from
[Parameter(Mandatory=$true, HelpMessage="The folder you are running Ombi from")][string]$OmbiDir,
# The address Ombi is listening on (default is http://localhost:5000
[Parameter(HelpMessage="The address Ombi is listening on (default is http://localhost:5000")][string]$OmbiURL = "http://localhost:5000",
# The folder to store downloads in temporarily
[Parameter(HelpMessage="The folder you want Ombi to download to temporarily")][string]$UpdaterPath = "$env:userprofile\Downloads\Ombi-Updates\",
# The name of the Ombi Service (Default: Ombi, can override)
[Parameter(HelpMessage="The name of the Ombi Service (Default: Ombi, can override)")][string]$ServiceName = "Ombi",
# The filename of the Ombi download
[Parameter(HelpMessage="Filename of the Ombi archive to download")][string]$Filename = "Win10-x64.zip",
# Is this a forced reinstall?
[Parameter(HelpMessage="Is this a forced reinstall?")][Switch]$Force
)
#endregion
#region Get-CurrentDetails (array.version)
function Get-CurrentDetails
{
param($URL,$HeaderValues)
try {
$result = Invoke-RestMethod -Uri $URL/api/v1/Settings/about/ -Headers $HeaderValues
return $result
} catch {
$result = $_.Exception.Response.GetResponseStream()
$reader = New-Object System.IO.StreamReader($result)
$reader.BaseStream.Position = 0
$reader.DiscardBufferedData()
return $result
}
return $result
}
#endregion
#region Get-NewVersion
function Get-NewVersion
{
$tag = (Invoke-WebRequest "https://api.github.com/repos/Ombi-app/Ombi/releases" | ConvertFrom-Json)[0].tag_name
$tag = $tag -replace '[v]'
return $tag
}
#endregion
#region API headers (for building the query to the application)
$headers = @{}
$headers.Add('Apikey',$APIKey)
$headers.Add('accept','application/json')
#endregion
#region Generated Variables (UpdateNeeded, OmbiCurrent.array, OmbiUpdate.array, TodayDate, DLFile, DLSource, BackupFile)
[bool]$UpdateNeeded = $false
$OmbiCurrent = Get-CurrentDetails -URL $OmbiURL -HeaderValues $headers
$OmbiUpdate = Get-NewVersion
$download = "https://github.com/Ombi-app/Ombi/releases/download/v$OmbiUpdate/$Filename"
$name = $Filename.Split(".")[0]
$zip = "$name-v$OmbiUpdate.zip"
$dir = "$name-v$OmbiUpdate"
#endregion
#region Compare current version to latest version, define $UpdateNeeded
if ($OmbiCurrent.version -ne $OmbiUpdate) {
$UpdateNeeded = $true}
#endregion
if ($UpdateNeeded -or $Force -and -not $UpdateError)
#region Update is needed, continue
{
#region Notify of version change and update
Write-Host ("There is an update pending. Current: " + $OmbiCurrent.version + ", Latest: " +$OmbiUpdate)
New-Item -Path $UpdaterPath -ItemType Directory -Force -ErrorAction SilentlyContinue | Out-Null
#region Ryder Stuff
Write-Host Stopping Ombi Service
Stop-Service $ServiceName -Force

Write-Host Dowloading latest release
Set-Location -Path $UpdaterPath
Invoke-WebRequest $download -Out $zip

Write-Host Extracting release files
Expand-Archive $zip -Force

Write-Host Backing up Ombi sqlite database if present
Copy-Item $OmbiDir\OmbiExternal.db $dir -Force -ErrorAction SilentlyContinue
Copy-Item $OmbiDir\Ombi.db $dir -Force -ErrorAction SilentlyContinue
Copy-Item $OmbiDir\OmbiSettings.db $dir -Force -ErrorAction SilentlyContinue

Write-Host Backing up Ombi MySQL settings if present
Copy-Item $OmbiDir\database.json $dir -Force -ErrorAction SilentlyContinue

Write-Host Deleting Ombi folder
Remove-Item $OmbiDir\* -Recurse -Force

Write-Host Moving new release files
Move-Item $dir\* -Destination $OmbiDir -Force

Write-Host Starting Ombi
Start-Service Ombi

Write-Host Cleaning up
Remove-Item $zip -Force
Remove-Item $dir -Force
#endregion
#endregion
}
else
{
Write-Host ($OmbiCurrent.version + " is the latest version.")
}
#endregion
Start-Sleep -s 5
