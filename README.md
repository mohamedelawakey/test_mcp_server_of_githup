# Git Pasha MCP Server

Simple MCP server for managing Git Pasha repositories.

## File Structure

```
gitpasha-mcp/
├── server.py           # Main MCP server
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── .env                # Your actual API key (create this)
└── README.md           # This file
```

## Features

- ✅ Create new repositories (with auto-suggested descriptions)
- ✅ Delete existing repositories
- ✅ Edit repository details
- ✅ List all repositories
- ✅ Get description suggestions

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup API Key

Copy `.env.example` to `.env` and add your Git Pasha API key:

```bash
cp .env.example .env
```

Edit `.env` and add your key:
```
GITPASHA_API_KEY=your_actual_key_here
```

Get your API key from: https://app.gitpasha.com/settings

### 3. Run Locally

```bash
python server.py
```

### 4. Add to Claude Desktop

Edit Claude config file:

**Mac/Linux:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add this:

```json
{
  "mcpServers": {
    "gitpasha": {
      "command": "python",
      "args": ["C:\\Users\\Yours\\Desktop\\MCP Server\\git basha\\server.py"]
    }
  }
}
```

#### > 📝 **Important Note**
Make sure to go to the following path:
```bash
C:\Users\Alawakey\AppData\Local\AnthropicClaude\app-0.13.64\logs\gitpasha.log 
```

- If you find the file `logs\gitpasha.log` ✅ — everything is fine, and the server can run properly.  
- If the file **doesn’t exist** ❌ — you need to **create it manually** so the server can start correctly.


## Usage Examples

### Create Repository
```
Create a new repo called "my-awesome-api"
```
Auto-suggests: "RESTful API service"

### Edit Repository
```
Edit repo "old-name" to have description "New description"
```

### Delete Repository
```
Delete repo "test-repo" with confirmation
```

### List Repositories
```
Show me all my repositories
```

## Tools Available

1. **create_repo** - Create new repository
2. **delete_repo** - Delete repository (requires confirmation)
3. **edit_repo** - Update repository settings
4. **list_repos** - List all repositories
5. **get_description_suggestion** - Get description idea for repo name

## Notes

- All descriptions are auto-suggested in English
- Simple and clean code
- Works locally and with Claude Desktop
- Requires Git Pasha API key