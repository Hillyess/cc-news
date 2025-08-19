# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the **refactored news status line plugin**.

## Project Overview

This is a **simplified version** of the Claude Code status line news plugin that provides real-time news ticker functionality with minimal complexity. The system consists of a single integrated news service and a streamlined status line display script.

**Current Version:** v2.0-refactored - Simplified architecture, removed translation complexity
**Status Line Format:** `[Time] [News Content with OSC 8 Hyperlinks]`

### Quick Start

Run the automated setup script to configure everything in one command:

```bash
cd refactored-news-statusline
./setup.sh
```

This script will:
- Set up Python virtual environment
- Install minimal dependencies (requests, beautifulsoup4)
- Configure Claude Code hooks and status line for refactored version
- Test the complete functionality

## Architecture

### Core Components (Simplified)

1. **news_service.py** - **Integrated service** (372 lines) that:
   - Scrapes news from multiple sources (36kr, TechCrunch, 虎嗅)
   - Maintains an in-memory news pool with automatic refresh
   - Provides HTTP API endpoints on port 8765
   - Handles deduplication and content filtering
   - **Removed**: Translation functionality, language detection, Claude Code integration

2. **status_line.sh** - **Streamlined display script** (140 lines) that:
   - Fetches news from the background service
   - Formats output with OSC 8 hyperlinks for Claude Code status line
   - Provides fallback content when service is unavailable
   - **Removed**: Translation logic, language configuration, complex formatting

3. **setup.sh** - **Simplified configuration script** that:
   - Sets up Python virtual environment with minimal dependencies
   - Configures Claude Code settings with correct absolute paths
   - Tests functionality without translation components

### Data Flow (Simplified)

```
News Sources → NewsService → HTTP API → Status Line Script → Claude Code UI
```

**Removed Components:**
- Translation Service (translation_service.py)
- Language detection and configuration
- Claude Code subprocess translation calls
- Batch translation with JSON parsing

## Development Commands

### Service Management

```bash
# Start news service manually (using relative virtual environment)
../venv/bin/python3 news_service.py

# Check service status
curl http://localhost:8765/status

# Get next news item (with time-based rotation)
curl http://localhost:8765/next

# Get random news
curl http://localhost:8765/random?count=5

# Manual refresh
curl http://localhost:8765/refresh
```

### Setup and Configuration

#### Automated Setup (Recommended)

```bash
cd refactored-news-statusline
./setup.sh
```

#### Manual Setup

```bash
# Use parent directory's virtual environment
source ../venv/bin/activate

# Install minimal dependencies
pip install requests beautifulsoup4

# Make scripts executable
chmod +x *.sh news_service.py

# Manually configure Claude Code (or use setup script)
```

### Testing

Test the refactored service:

```bash
# Test status line manually
echo '{"workspace":{"current_dir":"/test"}}' | ./status_line.sh

# Verify API endpoints
curl -s http://localhost:8765/status | jq .
curl -s http://localhost:8765/next | jq .
```

## Claude Code Integration

This refactored project integrates with Claude Code through simplified hooks configuration.

### Configuration Format (Claude Code v1.0.81+)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/didi/cc-status-line/refactored-news-statusline/../venv/bin/python3 /Users/didi/cc-status-line/refactored-news-statusline/news_service.py",
            "timeout": 30
          }
        ]
      },
      {
        "matcher": "resume",
        "hooks": [
          {
            "type": "command", 
            "command": "/Users/didi/cc-status-line/refactored-news-statusline/../venv/bin/python3 /Users/didi/cc-status-line/refactored-news-statusline/news_service.py",
            "timeout": 30
          }
        ]
      },
      {
        "matcher": "clear",
        "hooks": [
          {
            "type": "command",
            "command": "/Users/didi/cc-status-line/refactored-news-statusline/../venv/bin/python3 /Users/didi/cc-status-line/refactored-news-statusline/news_service.py", 
            "timeout": 30
          }
        ]
      }
    ]
  },
  "statusLine": {
    "type": "command",
    "command": "/Users/didi/cc-status-line/refactored-news-statusline/status_line.sh"
  }
}
```

### Status Line Output Format

The status line displays: `[Time] [News Content with Hyperlinks]`

Example: `15:42 🚀 AI-powered stuffed animals are coming for your kids`

**Key Features:**
- OSC 8 hyperlinks (click news titles to open URLs)
- Time-based intelligent rotation (30-second intervals)
- Source icons (💼 36kr, 🚀 TechCrunch, 🦆 虎嗅, 📰 other)
- Automatic title length management
- Fallback messages when service is unavailable
- **Removed**: Multi-language support, translation integration

## Key Implementation Details

### News Source Configuration

News sources are configured in `news_service.py` with CSS selectors for title extraction. Each source includes:
- Base URL and scraping endpoint
- Multiple CSS selector fallbacks
- Source-specific URL resolution logic
- **Simplified**: No language detection or translation preparation

### Error Handling and Resilience

- Service automatically retries failed news fetches
- Status line script provides fallback content when service is unavailable
- Graceful degradation with backup news messages
- Process management prevents duplicate service instances
- **Simplified**: No translation error handling or language fallbacks

### Performance Considerations

- News pool refreshes every 5 minutes (configurable)
- Maximum 100 news items in memory pool
- 6-hour content expiration
- Rate limiting: max 20 items per news source
- **Improved**: ~67% reduction in code size, faster startup

## Common Issues and Troubleshooting

### Configuration Issues

#### Claude Code hooks not working
- Verify hooks format matches the new Claude Code v1.0.81+ format
- Use absolute paths in hook commands
- Run `/doctor` in Claude Code to check configuration validity
- Use `./setup.sh` to auto-fix configuration

#### Settings.json errors
- Check JSON syntax: `cat ~/.claude/settings.json | jq .`
- Restore from backup if needed
- Re-run setup script to regenerate configuration

### Service Issues

#### Service Won't Start
- Check if port 8765 is available: `lsof -i :8765`
- Verify virtual environment: `ls -la ../venv/bin/python3`
- Check logs at `/tmp/news_service.log`
- Ensure dependencies are installed: `../venv/bin/python3 -c "import requests, bs4"`

#### No News Displaying
- Confirm service is running: `curl http://localhost:8765/status`
- Check script permissions: `ls -la *.sh`
- Test status line manually: `echo '{"workspace":{"current_dir":"/test"}}' | ./status_line.sh`
- Verify network connectivity for news source access

### Performance Issues

#### Slow status line updates
- Check news service response time: `time curl -s http://localhost:8765/next`
- Adjust `refresh_interval` in NewsPool (default: 300s)

#### Memory Usage
- Monitor service memory: `ps aux | grep news_service`
- Adjust `max_size` parameter in NewsPool constructor (default: 100)

## Dependencies

### Python Environment
- Python 3.x (tested with 3.12+)
- **Shared virtual environment**: `../venv/`
- **Minimal dependencies**: requests==2.31.0, beautifulsoup4==4.12.2

### System Requirements
- curl (for API testing and service checks)
- jq (for JSON processing in scripts)
- bash (for shell scripts)
- Modern terminal with OSC 8 hyperlink support

### Claude Code Requirements
- Claude Code v1.0.81+ (for new hooks format)
- Terminal with status line and OSC 8 support

## Refactoring Benefits

### Code Reduction
- **67% fewer lines**: 1,547 → 512 lines total
- **Simplified architecture**: 5+ files → 2 core files
- **Minimal dependencies**: Removed translation libraries

### Performance Improvements
- **Faster startup**: <2 seconds (removed translation initialization)
- **Lower memory**: ~37MB runtime footprint
- **Reduced complexity**: No language detection overhead

### Maintenance Benefits
- **Easier debugging**: Single integrated service
- **Simpler configuration**: Fewer configuration options
- **Focused functionality**: Core news aggregation only

## Version History

### v2.0-refactored (Current)
- ✅ Simplified 2-file architecture
- ✅ Removed translation complexity
- ✅ Maintained core news aggregation
- ✅ OSC 8 hyperlink support
- ✅ Time-based intelligent rotation
- ✅ 67% code reduction
- ✅ Improved performance and maintainability

### Removed Features (from v1.0)
- ❌ Multi-language translation
- ❌ Claude Code translation integration  
- ❌ Batch translation API
- ❌ Language detection and configuration
- ❌ Complex error handling for translation

### Future Considerations
- Consider translation as optional plugin
- Potential integration with external translation services
- Configuration-driven feature toggles