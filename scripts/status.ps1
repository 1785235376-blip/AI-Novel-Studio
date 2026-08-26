. $PSScriptRoot/common.ps1
$root=Get-ProjectRoot; $envs=Read-DotEnv $root
[pscustomobject]@{Project='AI Novel Studio';Profile=$envs['CREATION_PROFILE'];Docker=(Test-Command docker);Ollama=(Test-Command ollama);LocalModel=$envs['LOCAL_UTILITY_MODEL'];OpenAI=$(if($envs['OPENAI_API_KEY']){'Configured'}else{'Missing'});Anthropic=$(if($envs['ANTHROPIC_API_KEY']){'Configured'}else{'Missing'});NovelCount=@(Get-ChildItem (Join-Path $root 'novel_data/novels') -Directory).Count;FreeGB=[math]::Round((Get-PSDrive -Name ([IO.Path]::GetPathRoot($root).TrimEnd(':\'))).Free/1GB,1)} | Format-List
if (Test-Command docker) { docker compose --project-directory $root ps }

