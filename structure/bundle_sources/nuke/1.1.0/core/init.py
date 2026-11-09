"""
The Line Nuke Pipeline Initialization

This module initializes the Nuke pipeline environment and sets up global environment variables
for use by toolchains and other pipeline components.

The pipeline is localised as one bundle: this core folder sits next to toolchains/ inside it, so every
path is derived from this file and nothing depends on NUKE_PATH. NUKE_PATH belongs to the studio
bootstrap (and AYON) and is left untouched.

Environment Variables Set:
- TLA_COMP_CORE: This core directory (toolchains.json, config.json and icons live here)
- TLA_COMP_PIPELINE_ROOT: The bundle root, which holds core/ and toolchains/
- TLA_COMP_TOOLCHAINS: Directory containing all toolchain modules

Note: Template paths are now handled individually by each toolchain (e.g., TemplateTools)
rather than through global environment variables.
"""

import nuke
import os
import platform
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
PIPELINE_ROOT = CORE_DIR.parent


def release_version():
    """The localised release id. The bundle folder is named after it (.../hosts/nuke/<release>)."""
    return Path(os.environ.get('TLS_PIPELINE_NUKE') or PIPELINE_ROOT).name


def get_line_logo_with_version():
    """Get the LINE logo"""
    return f"""
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
     ___ _____ _   _ ___ ___ ___  
    / __|_   _| | | |   \_ _/ _ \ 
    \__ \ | | | |_| | |) | | (_) |
    |___/ |_|  \___/|___/___\___/ 
"""

# Static logo for backward compatibility
LINE_LOGO_STR = get_line_logo_with_version()

# Global reporter instance
PIPELINE_REPORTER = None


# Import pipeline logger and reporter
try:
    from utils.PipelineLogger import get_logger, log_performance
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False

# Import pipeline reporter
try:
    from utils.PipelineReporter import create_reporter
    REPORTER_AVAILABLE = True
except ImportError:
    REPORTER_AVAILABLE = False

# Check if debug mode is enabled
DEBUG_MODE = False
try:
    import json
    from pathlib import Path
    config_file = Path(__file__).parent / 'config.json'
    if config_file.exists():
        with config_file.open('r') as f:
            config = json.load(f)
            DEBUG_MODE = config.get('development', {}).get('debug_mode', False)
except:
    pass

# Initialize reporter
if REPORTER_AVAILABLE:
    PIPELINE_REPORTER = create_reporter(DEBUG_MODE)
    if not DEBUG_MODE:
        # Pass the dynamic logo to the reporter
        PIPELINE_REPORTER.print_initialization_header(get_line_logo_with_version())
    else:
        # Show ASCII art in debug mode
        print(get_line_logo_with_version())
else:
    print(get_line_logo_with_version())

# Initialize logger only if in debug mode or reporter not available
logger = None
if LOGGER_AVAILABLE and (DEBUG_MODE or not REPORTER_AVAILABLE):
    logger = get_logger("init")
    logger.info("===== INITIALIZING THE LINE NUKE PIPELINE =====")

def get_pipeline_paths():
    """Get all pipeline paths. They follow from where this core folder sits inside the bundle."""
    paths = {
        'TLA_COMP_CORE': CORE_DIR,
        'TLA_COMP_PIPELINE_ROOT': PIPELINE_ROOT,
        'TLA_COMP_TOOLCHAINS': PIPELINE_ROOT / 'toolchains'
    }

    if logger:
        logger.info("Pipeline paths derived from the core location:")
        for key, path in paths.items():
            logger.info(f"  {key}: {path}")

    return paths

def set_pipeline_environment_variables(pipeline_paths, debug_mode=False, logger=None):
    """
    Set global environment variables for pipeline paths.
    
    Args:
        pipeline_paths (dict): Dictionary of path names and values
        debug_mode (bool): Whether to log debug information
        logger: Logger instance for debug output
    """
    if debug_mode and logger:
        logger.info("Setting global environment variables for pipeline")
    
    for key, path in pipeline_paths.items():
        os.environ[key] = str(path)
        if debug_mode and logger:
            logger.debug(f"Set {key} = {path}")
    
    if debug_mode and logger:
        logger.info(f"Successfully set {len(pipeline_paths)} environment variables")

def log_environment_info():
    """Log useful environment and system information for debugging"""
    if not logger:
        return
    
    logger.debug("=== ENVIRONMENT INFORMATION ===")
    
    # Nuke version and build info
    try:
        nuke_version = nuke.NUKE_VERSION_STRING
        logger.debug(f"Nuke Version: {nuke_version}")
    except:
        logger.debug("Nuke version information not available")
    
    # Python version
    import sys
    logger.debug(f"Python Version: {sys.version}")
    logger.debug(f"Python Executable: {sys.executable}")
    
    # Current working directory
    logger.debug(f"Current Working Directory: {os.getcwd()}")
    
    # Key environment variables
    env_vars_to_log = ['NUKE_PATH', 'HOME', 'USER', 'USERNAME', 'COMPUTERNAME', 'PATH']
    for var in env_vars_to_log:
        value = os.environ.get(var, 'Not Set')
        if var == 'PATH':
            # PATH can be very long, so just log if it's set
            logger.debug(f"Environment Variable {var}: {'Set' if value != 'Not Set' else 'Not Set'}")
        else:
            logger.debug(f"Environment Variable {var}: {value}")
    
    logger.debug("=== END ENVIRONMENT INFORMATION ===")

# ============================================================================
# CROSS-PLATFORM FILENAME FILTER
# ============================================================================
# Register early — before any toolchains are loaded.
def filenameFix(filename):
    mappings = [
        ("/Volumes/Production/", "P:\\"),
        ("/Volumes/The Line/",   "Y:\\"),
    ]
    if platform.system() in ("Windows", "Microsoft"):
        for unix_path, win_path in mappings:
            filename = filename.replace(unix_path, win_path)
    else:
        for unix_path, win_path in mappings:
            filename = filename.replace(win_path, unix_path)
    return filename

nuke.addFilenameFilter(filenameFix)
if logger:
    logger.info("Cross Platform filename filter added")
else:
    print("Cross Platform filename filter added")
# ============================================================================

# Initialize pipeline paths early in the process
if DEBUG_MODE and logger:
    print("Setting up pipeline environment...")
    logger.info("Setting up pipeline environment")
    log_environment_info()

import time
start_time = time.time()

# Get all pipeline paths, derived from this core folder
pipeline_paths = get_pipeline_paths()

# Validate that paths exist
if DEBUG_MODE and logger:
    logger.debug("Validating pipeline paths...")

path_validation_errors = []
for key, path in pipeline_paths.items():
    if not Path(path).exists():
        error_msg = f"Path does not exist: {key} = {path}"
        path_validation_errors.append(error_msg)
        if DEBUG_MODE and logger:
            logger.warning(error_msg)

if path_validation_errors and DEBUG_MODE and logger:
    logger.warning(f"Found {len(path_validation_errors)} path validation issues")
elif DEBUG_MODE and logger:
    logger.debug("All pipeline paths validated successfully")

# ============================================================================
# SET GLOBAL ENVIRONMENT VARIABLES FOR PIPELINE
# ============================================================================
# Export all pipeline paths as environment variables for toolchains and other scripts
set_pipeline_environment_variables(pipeline_paths, DEBUG_MODE, logger)

if DEBUG_MODE and logger:
    print("Pipeline environment variables exported successfully")
# ============================================================================

# Set environment data for reporter
if REPORTER_AVAILABLE:
    PIPELINE_REPORTER.set_environment_data(pipeline_paths)
    PIPELINE_REPORTER.print_environment_summary()

# Display pipeline environment information in console
def show_pipeline_environment():
    """Display key pipeline environment variables in a nice format."""
    version = release_version()
    
    pipeline_vars = {
        'TLA_COMP_CORE': os.environ.get('TLA_COMP_CORE', 'Not Set'),
        'TLA_COMP_PIPELINE_ROOT': os.environ.get('TLA_COMP_PIPELINE_ROOT', 'Not Set'),
        'TLA_COMP_TOOLCHAINS': os.environ.get('TLA_COMP_TOOLCHAINS', 'Not Set')
    }
    
    print("="*70)
    print(f"  INITIALIZING THE LINE NUKE PIPELINE v{version}")
    print("="*70)
    
    # Find the longest key for alignment
    max_key_length = max(len(key) for key in pipeline_vars.keys())
    
    for key, value in pipeline_vars.items():
        # Truncate very long paths for readability
        display_value = value
        if len(value) > 50:
            display_value = "..." + value[-47:]
        
        print(f"  {key:<{max_key_length}} : {display_value}")
    
    print("="*70)

# Show pipeline environment variables
show_pipeline_environment()

# Log performance metrics
setup_time = time.time() - start_time
if LOGGER_AVAILABLE and DEBUG_MODE and logger:
    log_performance("pipeline_initialization", setup_time, {
        "paths_configured": len(pipeline_paths),
        "validation_errors": len(path_validation_errors)
    })

if DEBUG_MODE:
    if logger:
        logger.info(f"===== THE LINE NUKE PIPELINE SETUP COMPLETE ({setup_time:.3f}s) =====")
    else:
        print(f"The Line Nuke Pipeline - Setup Complete ({setup_time:.3f} seconds)")
