<p align="center">
  <img src="docs/line_logo_red.png" alt="The Line Logo" style="max-width: 600px; width: 100%;" />
</p>

# Nuke Pipeline

A modular, configuration-driven pipeline system for Nuke that provides a flexible foundation for VFX workflows through toolchains and template management.

<p align="center">
  <img src="docs/pipeline.png" alt="Pipeline Architecture Diagram" style="max-width: 700px; width: 100%;" />
</p>

## Core Concepts

### 🔧 **Toolchains**
Toolchains are modular collections of tools, gizmos, and scripts that can be enabled/disabled independently. Each toolchain is self-contained and configurable through JSON.

**Examples:**
- **TemplateTools**: Template creation, saving, and loading system
- **TheLine**: Custom studio-specific tools and workflows
- **NukeSurvivalToolkit**: Third-party compositing utilities
- **Stamps**: Node annotation and organization tools

### 📋 **Template System**
The template system allows artists to save and share common node setups with associated assets and metadata.

<p align="center">
  <img src="docs/templates.png" alt="Template Dialog UIs" style="max-width: 700px; width: 100%;" />
</p>

**Features:**
- **Visual Previews**: Automatic MP4 generation for template previews
- **Asset Management**: Automatic copying and path management for Read nodes
- **Metadata**: Tags, descriptions, author info, and node counts
- **Searchable**: Tags and filenames fully searchable 
- **Compatibility**: PySide2/6 compatible interface

### 🏗️ **Pipeline Architecture**

```
Y:\PIPELINE\config\nuke\
├── core/0.0.1/              # Core pipeline system
│   ├── init.py              # Pipeline initialization
│   ├── menu.py              # Menu and startup configuration
│   ├── config.py            # Configuration management
│   ├── toolchains.py        # Toolchain loader
│   └── utils/               # Utility modules
├── toolchains/              # Modular tool collections
│   ├── TemplateTools/1.0.0/ # Template management system
│   ├── TheLine/0.0.1/       # Studio-specific tools
│   └── [other toolchains]/  # Additional tool collections
└── templates/               # Template library storage
    ├── 2DFX/                # Category-based organization
    ├── 3D/                  # 3D-specific templates
    └── Utilities/           # General utility templates
```

## Key Features

### 🎛️ **Configuration-Driven**
- JSON-based configuration for easy customization
- Environment-specific settings (Windows/Mac)
- Debug modes and logging controls
- Grid preferences and UI customization

### 🔌 **Modular Design**
- Enable/disable toolchains independently
- Priority-based loading order
- Automatic discovery of new tools
- Isolated environments prevent conflicts

### 📁 **Template Management**
- **Save Templates**: Convert node selections to reusable templates
- **Load Templates**: Browse and load templates with visual previews
- **Asset Handling**: Automatic path management for external assets
- **Metadata**: Rich information including tags, descriptions, and previews

### 🖥️ **Modern UI**
- PySide2/6 compatible for Nuke 11-16+
- Dark theme matching Nuke's interface
- Tag-based search and filtering
- Video preview capabilities
- Right-click context menus

## Getting Started

### Prerequisites
- Nuke 11.0 or later
- Python 3.6+ (included with Nuke)
- Access to pipeline network drive

### Setup
1. Set `NUKE_PATH` environment variable to `Y:\PIPELINE\config\nuke\core\0.0.1`
2. Launch Nuke - the pipeline will initialize automatically
3. Check the console for successful initialization messages

### Using Templates
1. **Create Templates**: Select nodes → Template Tools → Save Template
2. **Load Templates**: Template Tools → Template Loader
3. **Browse**: Use tags and search to find templates
4. **Load**: Double-click or use Load button to import templates

## Configuration

### Toolchain Configuration
Edit `core/0.0.1/toolchains.json` to:
- Enable/disable toolchains
- Set loading priorities
- Configure toolchain-specific settings
- Set template storage locations

### Environment Variables
- `NUKE_PATH`: Points to core pipeline directory
- `TLA_COMP_PIPELINE_ROOT`: Pipeline root directory
- `TLA_COMP_TOOLCHAINS`: Toolchains directory

## Development

### Adding New Toolchains
1. Create toolchain directory in `toolchains/`
2. Add entry to `toolchains.json`
3. Include `init.py` and `menu.py` in toolchain
4. Set appropriate priority and dependencies

### Template System Architecture
- **template_library.py**: Core template management
- **template_loader_ui.py**: Modern browsing interface
- **template_save_ui.py**: Template creation interface
- **widgets.py**: Custom UI components

## Troubleshooting

### Common Issues
- **Templates not loading**: Check template root path in configuration
- **Toolchains missing**: Verify `NUKE_PATH` environment variable
- **UI not appearing**: Ensure PySide2/6 compatibility

### Debug Mode
Enable debug mode in `core/0.0.1/config.json`:
```json
{
  "development": {
    "debug_mode": true
  }
}
```

## Support

For issues or questions about the pipeline:
- Check console output for error messages
- Review log files in `core/0.0.1/logs/`
- Consult pipeline documentation
- Contact pete@thelinestudio.com

---

**Version**: 0.0.1  
**Last Updated**: July 2025  
**Maintained by**: Pete Addington
**Vibe Coded with**: Copilot
