Faststack MCP + Claude Code Process

This runbook is for using `faststack_mcp` with Claude Code in this project.

## 1) Confirm server is connected

From project root:

```powershell
claude mcp list
claude mcp get faststack
```

Expected status: `Connected`.

## 2) If faststack is missing, add it

If `faststack` is not listed:

```powershell
claude mcp add -s local faststack .\.venv\Scripts\faststack-mcp.exe
```

Then verify again:

```powershell
claude mcp list
```

## 3) Start Claude in this repo

```powershell
claude
```

## 4) First prompt in Claude: index this project

Use this prompt:

```text
Use mcp__faststack__index_folder on path "." with force=true.
Return only project_id, file_count, symbol_count, and detected_languages.
```

Save the returned `project_id` for later calls.

## 5) Explore the project structure

Use:

```text
Use mcp__faststack__get_project_outline for project_id "<PROJECT_ID>".
```

Optional:

```text
Use mcp__faststack__get_file_tree for project_id "<PROJECT_ID>".
```

## 6) Find and inspect code quickly

Find symbol:

```text
Use mcp__faststack__search_symbols for project_id "<PROJECT_ID>" and query "AuthService".
```

Open exact symbol snippet:

```text
Use mcp__faststack__get_symbol for project_id "<PROJECT_ID>" and symbol_id "<SYMBOL_ID>".
```

Text fallback:

```text
Use mcp__faststack__search_text for project_id "<PROJECT_ID>" and query "JWT refresh token".
```

## 7) Refresh index after major changes

```text
Use mcp__faststack__invalidate_cache for project_id "<PROJECT_ID>".
Then run mcp__faststack__index_folder on "." with force=true.
```

## 8) Useful note on env files

By default, `.env.example` is indexed and sensitive values are masked.  
Real `.env` files are skipped unless `include_env_files=true` is explicitly used during indexing.

