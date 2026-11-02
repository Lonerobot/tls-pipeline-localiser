"""
The Line Nuke Pipeline Initialization

This module initializes the Nuke pipeline environment and sets up global environment variables
for use by toolchains and other pipeline components.

Environment Variables Set:
- NUKE_PATH: Path to the core pipeline directory
- TLA_COMP_PIPELINE_ROOT: Root directory of the Nuke pipeline
- TLA_COMP_TOOLCHAINS: Directory containing all toolchain modules

Note: Template paths are now handled individually by each toolchain (e.g., TemplateTools)
rather than through global environment variables.
"""

import nuke
import os
import platform
from pathlib import Path



def get_line_logo_with_version():
    """Get the LINE logo with dynamic version from NUKE_PATH"""
    # Get version from NUKE_PATH or fallback
    nuke_path = os.environ.get('NUKE_PATH', 'Y:/PIPELINE/config/nuke/core/0.0.1')
    version = Path(nuke_path).name  # Gets the last folder name (e.g., "0.0.1")
    
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
    """Get all pipeline paths from NUKE_PATH environment variable"""
    if logger:
        logger.debug("Getting pipeline paths from environment variables")
    
    nuke_path = os.environ.get('NUKE_PATH')
    if logger:
        logger.debug(f"NUKE_PATH environment variable: {nuke_path}")
    
    if nuke_path:
        # Handle AYON case where NUKE_PATH is a semicolon-separated list
        if ';' in nuke_path:
            if logger:
                logger.debug("Detected semicolon-separated NUKE_PATH (likely AYON environment)")
            
            # Split the paths and find the one that contains our pipeline
            nuke_path_list = nuke_path.split(';')
            pipeline_path = None
            
            for path in nuke_path_list:
                path = path.strip()
                # Look for paths containing PIPELINE and either 'core' or that end with a version pattern
                if 'PIPELINE' in path and ('core' in path or any(char.isdigit() for char in Path(path).name)):
                    pipeline_path = path
                    if logger:
                        logger.debug(f"Found pipeline path in list: {pipeline_path}")
                    break
            
            if not pipeline_path:
                if logger:
                    logger.warning("Could not find pipeline path in NUKE_PATH list, using first path")
                pipeline_path = nuke_path_list[0].strip()
            
            nuke_core_path = Path(pipeline_path)
        else:
            # Single path case (normal operation)
            nuke_core_path = Path(nuke_path)
        
        if logger:
            logger.debug(f"Using NUKE_PATH: {nuke_core_path}")
        
        # Calculate all the pipeline paths
        # Handle different folder structures: core/X.X.X or any version folder under nuke
        if nuke_core_path.parent.name == 'core':
            # Standard structure: .../nuke/core/X.X.X
            pipeline_root = nuke_core_path.parent.parent  # Go back 2 levels: core/X.X.X -> nuke
        elif 'PIPELINE' in str(nuke_core_path.parent):
            # Alternative structure: .../PIPELINE/config/nuke/X.X.X
            pipeline_root = nuke_core_path.parent  # Go back 1 level to nuke folder
        else:
            # Fallback: assume we're in a version folder under nuke
            pipeline_root = nuke_core_path.parent
        
        toolchains_path = pipeline_root / 'toolchains'
        
        paths = {
            'NUKE_PATH': nuke_core_path,
            'TLA_COMP_PIPELINE_ROOT': pipeline_root,
            'TLA_COMP_TOOLCHAINS': toolchains_path
        }
        
        if logger:
            logger.info("Pipeline paths calculated from NUKE_PATH:")
            for key, path in paths.items():
                logger.info(f"  {key}: {path}")
        
        return paths
    
    # Fallback paths if NUKE_PATH isn't set
    if logger:
        logger.warning("NUKE_PATH not set, using fallback paths")
    
    default_root = Path('Y:/PIPELINE/config/nuke')
    fallback_paths = {
        'NUKE_PATH': default_root / 'core' / '0.0.1',
        'TLA_COMP_PIPELINE_ROOT': default_root,
        'TLA_COMP_TOOLCHAINS': default_root / 'toolchains'
    }
    
    if logger:
        logger.info("Using fallback pipeline paths:")
        for key, path in fallback_paths.items():
            logger.info(f"  {key}: {path}")
    
    return fallback_paths

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

# Get all pipeline paths from NUKE_PATH
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
    # Get version from NUKE_PATH or fallback
    nuke_path = os.environ.get('NUKE_PATH', 'Y:/PIPELINE/config/nuke/core/0.0.1')
    version = Path(nuke_path).name  # Gets the last folder name (e.g., "0.0.1")
    
    pipeline_vars = {
        'NUKE_PATH': os.environ.get('NUKE_PATH', 'Not Set'),
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
