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

# These keys have intentionally improved player-facing AP labels while the old
# client factory still uses a typo or a less accurate name for the same grant.
$registryAliases = @{
    "ITEM_BP_MS_CHARM_MONROE" = "Blueprint: Ms. Charm Monroe"
    "ITEM_BP_EMPTY_GARDEN_BED" = "Blueprint: Empty garden bed"
    "ITEM_BP_ZOMBIE_STONE_QUARRY" = "Blueprint: Zombie stone mine"
    "ITEM_BP_ZOMBIE_MARBLE_QUARRY" = "Blueprint: Zombie marble mine"
    "ITEM_LEARN_CREATE_PRAY_FOR_SOULS_REPOSE" = "Create: Prayer for souls' repose"
    "ITEM_LEARN_CREATE_PRAY_FOR_SOULS_CONTENTMENT" = "Create: Prayer for souls' contentment"
    "ITEM_LEARN_CREATE_PRAY_FOR_SOULS_THOROUGH_CLEANSING" = "Create: Prayer for souls' thorough cleansing"
    "ITEM_LEARN_CREATE_WOODEN_GRAVE_FENCE" = "Create: Wodden grave fence"
    "ITEM_LEARN_CREATE_PROGRESSIVE_METAL_PARTS" = "Create: Progressive Metal Parts"
    "ITEM_LEARN_CREATE_MARBLE_REPAIR_KIT" = "Create: Marble repair kit"
}

# Corrections established directly from the raw game data rather than copied
# from the client factory. Martial skills grants p_big_guy (techs_data.json),
# and the human soul healing workstation is the named craft_obj_data entry.
$manualGrants = @{
    "ITEM_PERK_BIG_GUY" = [ordered]@{
        type = "perk_unlock"
        perk_id = "p_big_guy"
        craft_ids = [System.Collections.Generic.List[string]]::new()
        work_ids = [System.Collections.Generic.List[string]]::new()
    }
    "ITEM_BP_HUMAN_SOUL_HEALING" = [ordered]@{
        type = "craft_unlock"
        craft_ids = [System.Collections.Generic.List[string]] @(
            "souls_builddesk::soul_healing_for_human"
        )
    }
}

# The AP unlock groups name the root technology regions in their `researches`
# field. The corresponding values below are the real TechDefinition IDs from
# techs_data.json (also mirrored by the old client TechIds table). Receiving a
# group must unlock these roots so the player can buy their descendants. The
# two zombie groups intentionally have no root to auto-research: their item is
# an AP access gate only, while the game reveals those technologies through
# the normal quest progression.
$researchTechIdsByItemKey = @{
    "ITEM_UNLOCK_ANATOMY" = @("First slice")
    "ITEM_UNLOCK_ALCHEMY" = @("The Beginning Of Alchemy")
    "ITEM_UNLOCK_FAITH" = @("Faith")
    "ITEM_UNLOCK_GRAVES" = @("Grave plate")
    "ITEM_UNLOCK_WRITING" = @("Research")
    "ITEM_UNLOCK_FARMING" = @("Garden beds")
    "ITEM_UNLOCK_GATHERING" = @("Gathering")
    "ITEM_UNLOCK_SMITHING" = @("Iron")
    "ITEM_UNLOCK_WOOD" = @("The idea of the tree")
    "ITEM_UNLOCK_STONE" = @("The idea of the stone")
    "ITEM_UNLOCK_CLAY" = @("The idea of the earth")
    "ITEM_UNLOCK_SIMPLE_AND_TASTY" = @("2min")
    "ITEM_UNLOCK_VEGETABLE_DISHES" = @("Vegetable dishes")
    "ITEM_UNLOCK_JELLY" = @("Jelly desserts")
    "ITEM_UNLOCK_BREAD" = @("Bread")
    "ITEM_UNLOCK_FISH_DISHES" = @("Fish")
    "ITEM_UNLOCK_SWEET_BAKING" = @("Sweet baking")
    "ITEM_UNLOCK_EGG_DISHES" = @("French cuisine")
    "ITEM_UNLOCK_PIES" = @("Pies")
    "ITEM_UNLOCK_TASTY_AND_HEALTHY" = @("Vegetable bowl")
    "ITEM_UNLOCK_MEAT_FIESTA" = @("Fast food")
    "ITEM_UNLOCK_FISH_DELICACIES" = @("Fish delicous")
    "ITEM_UNLOCK_ZOMBIE_BASICS" = @()
    "ITEM_UNLOCK_ZOMBIE_WORKSTATIONS" = @()
    "ITEM_UNLOCK_SPIRITUALISM" = @("soul_sins_1")
}

$grants = [ordered]@{}
foreach ($entry in $items.GetEnumerator()) {
    $itemKey = [string] $entry.Key
    $itemData = $entry.Value
    $label = [string] $itemData.label

    if ($researchTechIdsByItemKey.ContainsKey($itemKey)) {
        $grants[$itemKey] = [ordered]@{
            type = "technology_unlock"
            technology_ids = Copy-StringList $researchTechIdsByItemKey[$itemKey]
        }
        continue
    }

    if ($manualGrants.ContainsKey($itemKey)) {
        $grants[$itemKey] = $manualGrants[$itemKey]
        continue
    }

    if ($registryAliases.ContainsKey($itemKey)) {
        $alias = $registryAliases[$itemKey]
        if (-not $registryEntries.ContainsKey($alias)) {
            throw "Client registry alias '$alias' for '$itemKey' does not exist."
        }
        $grants[$itemKey] = Convert-RegistryItemToGrant $registryEntries[$alias]
        continue
    }

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
