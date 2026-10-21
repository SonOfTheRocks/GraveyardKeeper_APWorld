param(
    [Parameter(Mandatory = $true)]
    [string] $ClientRoot,

    [string] $OutputPath = (
        Join-Path $PSScriptRoot "..\data\item_grants.json"
    )
)

$ErrorActionPreference = "Stop"

function Get-PrivateFieldValue {
    param(
        [Parameter(Mandatory = $true)]
        [object] $Object,

        [Parameter(Mandatory = $true)]
        [string] $Name
    )

    $type = $Object.GetType()
    $flags = [System.Reflection.BindingFlags] "Instance,Public,NonPublic,DeclaredOnly"
    while ($null -ne $type) {
        $field = $type.GetField($Name, $flags)
        if ($null -ne $field) {
            return $field.GetValue($Object)
        }
        $type = $type.BaseType
    }
    throw "Field '$Name' was not found on '$($Object.GetType().FullName)'."
}

function Copy-StringList {
    param([AllowNull()][object] $Values)

    $result = [System.Collections.Generic.List[string]]::new()
    if ($null -ne $Values) {
        foreach ($value in $Values) {
            $result.Add([string] $value)
        }
    }
    return ,$result
}

function Copy-StringStages {
    param([AllowNull()][object] $Stages)

    $result = [System.Collections.Generic.List[object]]::new()
    if ($null -ne $Stages) {
        foreach ($stage in $Stages) {
            $result.Add((Copy-StringList $stage))
        }
    }
    return ,$result
}

function Convert-RegistryItemToGrant {
    param([Parameter(Mandatory = $true)][object] $Item)

    $typeName = $Item.GetType().Name
    switch ($typeName) {
        "GKRecipe" {
            return [ordered]@{
                type = "craft_unlock"
                craft_ids = Copy-StringList (Get-PrivateFieldValue $Item "<IDs>k__BackingField")
            }
        }
        "GKProgressiveRecipe" {
            return [ordered]@{
                type = "progressive_craft_unlock"
                stages = Copy-StringStages (Get-PrivateFieldValue $Item "progressiveIDs")
            }
        }
        "GKWork" {
            return [ordered]@{
                type = "work_unlock"
                work_ids = Copy-StringList (Get-PrivateFieldValue $Item "<IDs>k__BackingField")
                perk_ids = Copy-StringList (Get-PrivateFieldValue $Item "_perks")
            }
        }
        "GKProgressiveWork" {
            return [ordered]@{
                type = "progressive_work_unlock"
                stages = Copy-StringStages (Get-PrivateFieldValue $Item "progressiveIDs")
            }
        }
        "GKPerk" {
            $perkIds = Copy-StringList (Get-PrivateFieldValue $Item "<IDs>k__BackingField")
            if ($perkIds.Count -ne 1) {
                throw "Expected one perk ID, found $($perkIds.Count)."
            }
            return [ordered]@{
                type = "perk_unlock"
                perk_id = $perkIds[0]
                craft_ids = Copy-StringList (Get-PrivateFieldValue $Item "_recipes")
                work_ids = Copy-StringList (Get-PrivateFieldValue $Item "_works")
            }
        }
        "GKPermaBuff" {
            $buffIds = Copy-StringList (Get-PrivateFieldValue $Item "<IDs>k__BackingField")
            if ($buffIds.Count -ne 1) {
                throw "Expected one permanent-buff ID, found $($buffIds.Count)."
            }
            return [ordered]@{
                type = "permanent_buff"
                buff_id = $buffIds[0]
                resource_types = Copy-StringList (Get-PrivateFieldValue $Item "_res_types")
                icon = [string] (Get-PrivateFieldValue $Item "_icon")
            }
        }
        "GKRelation" {
            $npcIds = Copy-StringList (Get-PrivateFieldValue $Item "<IDs>k__BackingField")
            if ($npcIds.Count -ne 1) {
                throw "Expected one NPC ID, found $($npcIds.Count)."
            }
            return [ordered]@{
                type = "relation"
                npc_id = $npcIds[0]
                amount = [int] (Get-PrivateFieldValue $Item "Amount")
            }
        }
        "GKIngameItem" {
            $itemIds = Copy-StringList (Get-PrivateFieldValue $Item "<IDs>k__BackingField")
            if ($itemIds.Count -ne 1) {
                throw "Expected one in-game item ID, found $($itemIds.Count)."
            }
            return [ordered]@{
                type = "game_item"
                item_id = $itemIds[0]
            }
        }
        default {
            throw "Unsupported client registry item type '$typeName'."
        }
    }
}

$clientAssemblyPath = Join-Path $ClientRoot "GraveyardKeepelago\bin\Debug\netstandard2.0\GraveyardKeepelago.dll"
if (-not (Test-Path $clientAssemblyPath)) {
    throw "Client assembly not found at '$clientAssemblyPath'. Build the client first."
}

$clientBin = Split-Path $clientAssemblyPath
[System.AppDomain]::CurrentDomain.add_AssemblyResolve({
    param($sender, $eventArgs)
    $dependencyName = ([System.Reflection.AssemblyName] $eventArgs.Name).Name + ".dll"
    $dependencyPath = Join-Path $clientBin $dependencyName
    if (Test-Path $dependencyPath) {
        return [System.Reflection.Assembly]::LoadFrom($dependencyPath)
    }
    return $null
})

$assembly = [System.Reflection.Assembly]::LoadFrom($clientAssemblyPath)
$registryType = $assembly.GetType("GraveyardKeepelago.Logic.GKItemRegistry", $true)
$factoryType = $assembly.GetType("GraveyardKeepelago.Logic.GKItemFactory", $true)
$registry = [System.Activator]::CreateInstance($registryType)
$factory = $factoryType.GetConstructors()[0].Invoke(@($null))
$factoryType.GetMethod("BuildAll").Invoke($factory, @($registry))

$registryEntries = @{}
$registryFlags = [System.Reflection.BindingFlags] "Instance,NonPublic"
foreach ($field in $registryType.GetFields($registryFlags)) {
    $dictionary = $field.GetValue($registry)
    foreach ($name in $dictionary.Keys) {
        if ($registryEntries.ContainsKey([string] $name)) {
            throw "Client registry name '$name' is registered more than once."
        }
        $registryEntries[[string] $name] = $dictionary[$name]
    }
}

$dataRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\data")).Path
$itemRoot = Join-Path $dataRoot "items"
$items = [ordered]@{}
foreach ($file in Get-ChildItem $itemRoot -Recurse -Filter "*.json" | Sort-Object FullName) {
    if ($file.FullName -match "[\\/]unused[\\/]") {
        continue
    }
    $fileItems = Get-Content -Raw $file.FullName | ConvertFrom-Json -AsHashtable
    foreach ($entry in $fileItems.GetEnumerator()) {
        if ($items.Contains($entry.Key)) {
            throw "AP item key '$($entry.Key)' is defined more than once."
        }
        $items[$entry.Key] = $entry.Value
    }
}

$keysByLabel = @{}
foreach ($entry in $items.GetEnumerator()) {
    $label = [string] $entry.Value.label
    if (-not $keysByLabel.ContainsKey($label)) {
        $keysByLabel[$label] = [System.Collections.Generic.List[string]]::new()
    }
    $keysByLabel[$label].Add([string] $entry.Key)
}

$grants = [ordered]@{}
foreach ($entry in $items.GetEnumerator()) {
    $itemKey = [string] $entry.Key
    $itemData = $entry.Value
    $label = [string] $itemData.label

    if ($keysByLabel[$label].Count -gt 1) {
        $grants[$itemKey] = [ordered]@{
            type = "TODO"
            reason = "Duplicate AP network label '$label' prevents an unambiguous client mapping."
        }
        continue
    }

    if ($registryEntries.ContainsKey($label)) {
        $grants[$itemKey] = Convert-RegistryItemToGrant $registryEntries[$label]
        continue
    }

    $relationMatch = [regex]::Match($label, "^(.*) - Happiness \+(\d+)$")
    if ($relationMatch.Success -and $registryEntries.ContainsKey($relationMatch.Groups[1].Value)) {
        $grant = Convert-RegistryItemToGrant $registryEntries[$relationMatch.Groups[1].Value]
        $grant.amount = [int] $relationMatch.Groups[2].Value
        $grants[$itemKey] = $grant
        continue
    }

    $reason = "No matching entry exists in the current client item registry."
    if ($itemKey.StartsWith("ITEM_UNLOCK_")) {
        $reason = "The client does not implement technology-group item delivery yet."
    }
    $grants[$itemKey] = [ordered]@{
        type = "TODO"
        reason = $reason
    }
}

$resolvedOutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$grants | ConvertTo-Json -Depth 20 | Set-Content -Encoding utf8 $resolvedOutputPath

$todoCount = @($grants.Values | Where-Object { $_.type -eq "TODO" }).Count
Write-Output "Exported $($grants.Count) item grants to '$resolvedOutputPath' ($todoCount TODO)."
