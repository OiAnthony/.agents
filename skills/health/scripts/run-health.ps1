param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("collect", "agent-context", "maintainability", "doc-refs", "verifier-output")]
    [string]$Action,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"

Remove-Item "Env:WAZA_PYTHON" -ErrorAction SilentlyContinue
Remove-Item "Env:DOC_REF_CHECKER" -ErrorAction SilentlyContinue
Remove-Item "Env:GIT_INSTALL_ROOT" -ErrorAction SilentlyContinue
Remove-Item "Env:BASH_ENV" -ErrorAction SilentlyContinue
Remove-Item "Env:ENV" -ErrorAction SilentlyContinue

function Test-PathWithinRoot([string]$Candidate, [string]$Root) {
    $candidatePath = [IO.Path]::GetFullPath($Candidate).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    )
    return $candidatePath.Equals(
        $rootPath,
        [StringComparison]::OrdinalIgnoreCase
    ) -or $candidatePath.StartsWith(
        $rootPath + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )
}

function Resolve-FinalPath([string]$Candidate) {
    if (-not $Candidate -or -not [IO.Path]::IsPathRooted($Candidate)) {
        return $null
    }
    try {
        $fullPath = [IO.Path]::GetFullPath($Candidate)
        $root = [IO.Path]::GetPathRoot($fullPath)
        $relative = $fullPath.Substring($root.Length)
        $parts = $relative.Split(
            [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar),
            [StringSplitOptions]::RemoveEmptyEntries
        )
        $current = $root
        $linksFollowed = 0
        foreach ($part in $parts) {
            $current = Join-Path $current $part
            $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
            while (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                $linksFollowed += 1
                if ($linksFollowed -gt 32) {
                    return $null
                }
                $target = $item.Target | Select-Object -First 1
                if (-not $target) {
                    return $null
                }
                if (-not [IO.Path]::IsPathRooted($target)) {
                    $target = Join-Path (Split-Path -Parent $item.FullName) $target
                }
                $current = [IO.Path]::GetFullPath($target)
                $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
            }
            $current = $item.FullName
        }
        return [IO.Path]::GetFullPath($current)
    } catch {
        return $null
    }
}

function ConvertTo-GitBashPath([string]$Candidate) {
    if (-not $Candidate) {
        return $null
    }
    try {
        $fullPath = [IO.Path]::GetFullPath($Candidate)
    } catch {
        return $null
    }
    if ($fullPath.StartsWith("\\")) {
        return "//" + $fullPath.TrimStart([char]'\').Replace('\', '/')
    }
    if (
        $fullPath.Length -ge 2 -and
        $fullPath[1] -eq ':' -and
        [char]::IsLetter($fullPath[0])
    ) {
        $drive = [char]::ToLowerInvariant($fullPath[0])
        $tail = $fullPath.Substring(2).Replace('\', '/').TrimStart('/')
        if ($tail) {
            return "/$drive/$tail"
        }
        return "/$drive"
    }
    return $fullPath.Replace('\', '/')
}

function Resolve-SafePath([string]$Candidate, [string]$TargetRoot) {
    if (-not $Candidate -or $Candidate.StartsWith("\\")) {
        return $null
    }
    try {
        $lexical = [IO.Path]::GetFullPath($Candidate)
        if (Test-PathWithinRoot $lexical $TargetRoot) {
            return $null
        }
        $final = Resolve-FinalPath $lexical
        if (-not $final -or (Test-PathWithinRoot $final $TargetRoot)) {
            return $null
        }
        return $final
    } catch {
        return $null
    }
}

function Resolve-Executable([string]$Candidate, [string]$TargetRoot) {
    if (-not $Candidate) {
        return $null
    }
    $source = $Candidate
    if (-not [IO.Path]::IsPathRooted($source)) {
        $command = Get-Command $source -ErrorAction SilentlyContinue
        if (-not $command) {
            return $null
        }
        $source = $command.Source
    }
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        return $null
    }
    return (Resolve-SafePath $source $TargetRoot)
}

function Test-GitBashRoot([string]$Root, [string]$TargetRoot) {
    if (-not $Root) {
        return $false
    }
    $safeRoot = Resolve-SafePath $Root $TargetRoot
    if (-not $safeRoot) {
        return $false
    }
    $bash = Resolve-Executable (Join-Path $safeRoot "bin\bash.exe") $TargetRoot
    if (-not $bash) {
        return $false
    }
    try {
        & $bash --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Find-GitRoot([string]$Executable, [string]$TargetRoot) {
    if (-not $Executable) {
        return $null
    }

    $safePath = Resolve-SafePath $Executable $TargetRoot
    if (-not $safePath) {
        return $null
    }
    $current = if (Test-Path -LiteralPath $safePath -PathType Container) {
        $safePath
    } else {
        Split-Path -Parent $safePath
    }
    while ($current) {
        if (
            (Test-Path -LiteralPath (Join-Path $current "bin\bash.exe") -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $current "usr\bin") -PathType Container) -and
            (Test-GitBashRoot $current $TargetRoot)
        ) {
            return $current
        }
        $parent = Split-Path -Parent $current
        if (-not $parent -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
    return $null
}

function Find-InstalledGitRoot([string]$TargetRoot) {
    $candidates = @()
    foreach ($key in @(
        "HKLM:\SOFTWARE\GitForWindows",
        "HKLM:\SOFTWARE\WOW6432Node\GitForWindows",
        "HKCU:\SOFTWARE\GitForWindows"
    )) {
        try {
            $installPath = (Get-ItemProperty -LiteralPath $key -ErrorAction Stop).InstallPath
            if ($installPath) {
                $candidates += $installPath
            }
        } catch {
            # A missing registry key is normal.
        }
    }

    $programFiles = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::ProgramFiles
    )
    $programFilesX86 = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::ProgramFilesX86
    )
    $localAppData = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData
    )
    foreach ($base in @($programFiles, $programFilesX86)) {
        if ($base) {
            $candidates += (Join-Path $base "Git")
        }
    }
    if ($localAppData) {
        $candidates += (Join-Path $localAppData "Programs\Git")
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        $root = Find-GitRoot $candidate $TargetRoot
        if ($root) {
            return $root
        }
    }
    return $null
}

function Get-SafePath([string]$TargetRoot) {
    $safeEntries = @()
    foreach ($entry in $env:PATH.Split([IO.Path]::PathSeparator)) {
        $candidate = $entry.Trim().Trim('"')
        if (-not $candidate -or -not [IO.Path]::IsPathRooted($candidate)) {
            continue
        }
        if ($candidate.StartsWith("\\")) {
            continue
        }
        try {
            $fullPath = Resolve-SafePath $candidate $TargetRoot
            if ($fullPath -and (Test-Path -LiteralPath $fullPath -PathType Container)) {
                $safeEntries += $fullPath
            }
        } catch {
            # Malformed inherited PATH entries are not executable roots.
        }
    }
    return ($safeEntries -join [IO.Path]::PathSeparator)
}

function Resolve-WorkingPython([string]$Candidate, [string]$TargetRoot) {
    $executable = Resolve-Executable $Candidate $TargetRoot
    if (-not $executable) {
        return $null
    }
    try {
        $probe = @(
            & $executable -I -c (
                "import sys; print('waza-health-python-ok') " +
                "if sys.version_info >= (3, 9) else sys.exit(1)"
            ) 2>$null
        )
        if (
            $LASTEXITCODE -eq 0 -and
            $probe.Count -eq 1 -and
            $probe[0] -eq "waza-health-python-ok"
        ) {
            return $executable
        }
    } catch {
        # App Execution Aliases and stale shims can resolve but not run.
    }
    return $null
}

function Find-Python([string]$TargetRoot) {
    foreach ($name in @("python3.exe", "python.exe")) {
        foreach ($entry in $env:PATH.Split([IO.Path]::PathSeparator)) {
            $directory = $entry.Trim().Trim('"')
            if (-not $directory -or -not [IO.Path]::IsPathRooted($directory)) {
                continue
            }
            $executable = Resolve-WorkingPython (Join-Path $directory $name) $TargetRoot
            if ($executable) {
                return $executable
            }
        }
    }

    $launcher = Resolve-Executable "py.exe" $TargetRoot
    if ($launcher) {
        try {
            $registered = & $launcher -3 -I -c "import sys; print(sys.executable)" 2>$null |
                Select-Object -First 1
            if ($LASTEXITCODE -eq 0 -and $registered) {
                $executable = Resolve-WorkingPython ($registered.Trim()) $TargetRoot
                if ($executable) {
                    return $executable
                }
            }
        } catch {
            # Continue to registered install locations.
        }
    }

    $candidates = @()
    $userProfile = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::UserProfile
    )
    $localAppData = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData
    )
    $programFiles = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::ProgramFiles
    )
    if ($userProfile) {
        $candidates += (Join-Path $userProfile "anaconda3\python.exe")
        $candidates += (Join-Path $userProfile "miniconda3\python.exe")
    }
    if ($localAppData) {
        $candidates += (Join-Path $localAppData "Programs\Python\Python*\python.exe")
    }
    if ($programFiles) {
        $candidates += (Join-Path $programFiles "Python*\python.exe")
    }
    foreach ($candidate in $candidates) {
        $matches = @(
            Resolve-Path -Path $candidate -ErrorAction SilentlyContinue |
                Sort-Object Path
        )
        foreach ($match in $matches) {
            $executable = Resolve-WorkingPython $match.Path $TargetRoot
            if ($executable) {
                return $executable
            }
        }
    }
    return $null
}

$scriptNames = @{
    "collect" = "collect-data.sh"
    "agent-context" = "check-agent-context.sh"
    "maintainability" = "check-maintainability.sh"
    "doc-refs" = "check-doc-refs.sh"
    "verifier-output" = "check-verifier-output.sh"
}
$scriptName = $scriptNames[$Action]
$scriptPath = Join-Path $PSScriptRoot $scriptName
if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) {
    [Console]::Error.WriteLine("Health runtime script not found: $scriptPath")
    exit 1
}

$bashPath = $null
$targetRoot = Resolve-FinalPath (Get-Location).Path
if (-not $targetRoot) {
    [Console]::Error.WriteLine("Health could not resolve the audited project root safely.")
    exit 1
}
if (
    $Action -ne "collect" -and
    $ScriptArgs.Count -gt 0 -and
    (Test-Path -LiteralPath $ScriptArgs[0] -PathType Container)
) {
    $targetRoot = Resolve-FinalPath ([IO.Path]::GetFullPath($ScriptArgs[0]))
    if (-not $targetRoot) {
        [Console]::Error.WriteLine("Health could not resolve the audited project root safely.")
        exit 1
    }
}
$childPath = Get-SafePath $targetRoot
$env:PATH = $childPath
$pythonPath = $null
$isWindowsHost = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
if ($isWindowsHost) {
    $gitRoot = Find-InstalledGitRoot $targetRoot
    if ($gitRoot -and -not (Test-GitBashRoot $gitRoot $targetRoot)) {
        $gitRoot = $null
    }
    if (-not $gitRoot) {
        $git = Resolve-Executable "git.exe" $targetRoot
        $bash = Resolve-Executable "bash.exe" $targetRoot
        $gitRoot = Find-GitRoot $git $targetRoot
        if (-not $gitRoot) {
            $gitRoot = Find-GitRoot $bash $targetRoot
        }
        if (-not $gitRoot -and $git) {
            $gitExecPath = & $git --exec-path 2>$null
            if ($LASTEXITCODE -eq 0) {
                $gitRoot = Find-GitRoot $gitExecPath $targetRoot
            }
        }
    }
    if (-not $gitRoot) {
        [Console]::Error.WriteLine(
            "Health requires Git for Windows with bin\bash.exe in a standard install or safe PATH."
        )
        exit 1
    }

    $bashPath = Resolve-Executable (Join-Path $gitRoot "bin\bash.exe") $targetRoot
    if (-not $bashPath) {
        [Console]::Error.WriteLine(
            "Health requires Git for Windows with bin\bash.exe in a standard install or safe PATH."
        )
        exit 1
    }
    $runtimeCandidates = @(
        (Join-Path $gitRoot "usr\bin"),
        (Join-Path $gitRoot "mingw64\bin"),
        (Join-Path $gitRoot "bin"),
        (Join-Path $gitRoot "cmd")
    )
    $runtimePaths = @()
    foreach ($candidate in $runtimeCandidates) {
        $safeRuntimePath = Resolve-SafePath $candidate $targetRoot
        if ($safeRuntimePath -and (Test-Path -LiteralPath $safeRuntimePath -PathType Container)) {
            $runtimePaths += $safeRuntimePath
        }
    }
    $pythonPath = Find-Python $targetRoot
    $pythonPaths = @()
    if ($pythonPath) {
        $pythonPaths += (Split-Path -Parent $pythonPath)
    }
    $childPath = (@($pythonPaths) + @($runtimePaths) + @($env:PATH)) -join [IO.Path]::PathSeparator
} else {
    $bashPath = Resolve-Executable "bash" $targetRoot
    if (-not $bashPath) {
        [Console]::Error.WriteLine("Health requires Bash on PATH.")
        exit 1
    }
}

$env:PATH = $childPath

$bashScriptPath = if ($isWindowsHost) {
    ConvertTo-GitBashPath $scriptPath
} else {
    $scriptPath
}
if (-not $bashScriptPath) {
    [Console]::Error.WriteLine("Health could not translate its runtime script path for Git Bash.")
    exit 1
}

& $bashPath -p $bashScriptPath @ScriptArgs
exit $LASTEXITCODE
