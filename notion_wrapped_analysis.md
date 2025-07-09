# Notion Wrapped - Repository Analysis

## Overview
This repository contains **Notion Wrapped**, a Python tool that analyzes your Notion workspace to generate "Spotify Wrapped" style analytics and visualizations about your Notion usage patterns.

## What It Does
The tool recursively processes your Notion workspace to produce:

### 📊 Analytics & Statistics
- **Block type distribution** (paragraphs, lists, pages, databases, etc.)
- **Word count analysis** with total words and estimated pages saved
- **User activity tracking** (who created/edited content)
- **Time-based patterns** (daily activity, hourly usage patterns)
- **Recursion depth analysis** (how nested your content structure is)

### 🎨 Visualizations
- **Network graph** showing page/block relationships and structure
- **Word cloud** from your content (with optional Notion logo mask)
- **Time plots** showing activity patterns over time
- **Daily activity charts** with usage statistics
- **Block type distribution charts**

### 🔍 Key Features
- **Recursive analysis** of your entire Notion workspace
- **API caching** to avoid rate limits and speed up repeated runs
- **Configurable depth limits** and filtering options
- **Anonymous mode** for privacy-sensitive network graphs
- **Multi-threaded processing** for faster analysis
- **Beautiful terminal output** with colored progress indicators

## How It Works
1. **Authentication**: Uses your Notion API token to access your workspace
2. **Recursion**: Starts from specified page IDs and recursively processes all child content
3. **Analysis**: Collects statistics on blocks, words, users, timestamps, and relationships
4. **Visualization**: Generates interactive network graphs, word clouds, and time-based charts
5. **Output**: Creates an `analytics/` folder with all results and visualizations

## Installation & Usage
This is a command-line tool installed via pip:
```bash
pip install notion-wrapped
notion-wrapped --notion-token YOUR_TOKEN --page-ids PAGE_ID_1 PAGE_ID_2
```

## Target Audience
Perfect for Notion power users who want to:
- Understand their workspace structure and usage patterns
- Get insights into their content creation habits
- Visualize the relationships between their pages and databases
- Share their "Notion Wrapped" results (similar to Spotify Wrapped)

The tool is designed to be both analytically useful and social media shareable, encouraging users to share their Notion usage with `#NotionWrapped`.