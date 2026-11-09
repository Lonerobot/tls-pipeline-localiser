# --- Patch live nukescripts.psd from our TL_BreakOutPSD copy ---
import os
import sys
import importlib
import importlib.util
import nuke
from pathlib import Path

# Import centralized pipeline logging
LOGGING_AVAILABLE = False
logger = None

try:
    from utils.PipelineLogger import get_logger
    logger = get_logger("TL_BreakOutPSD")
    LOGGING_AVAILABLE = True
except ImportError:
    try:
        from PipelineLogger import get_logger
        logger = get_logger("TL_BreakOutPSD")
        LOGGING_AVAILABLE = True
    except ImportError:
        LOGGING_AVAILABLE = False
        logger = None
except Exception:
    LOGGING_AVAILABLE = False
    logger = None

def log_message(message, level="info"):
    """
    Log message using pipeline logger or fallback to nuke.tprint
    
    Args:
        message (str): Message to log
        level (str): Log level - "info", "warning", "error", "debug"
    """
    # Always output to Nuke console for immediate visibility
    nuke.tprint(f"[TL_BreakOutPSD] {message}")
    
    # Also try to log through pipeline system if available
    if LOGGING_AVAILABLE and logger:
        try:
            if level == "info":
                logger.info(message)
            elif level == "warning":
                logger.warning(message)
            elif level == "error":
                logger.error(message)
            elif level == "debug":
                logger.debug(message)
            else:
                logger.info(message)
        except Exception as e:
            nuke.tprint(f"[TL_BreakOutPSD] Logging error: {e}")

def patch_nukescripts_psd():
    """
    Dynamically patch nukescripts.psd with our enhanced version.
    Uses relative paths based on this toolchain's location.
    """
    try:
        # 1) Get the path to our custom psd.py relative to this init.py file
        toolchain_dir = Path(__file__).parent
        custom_psd_path = toolchain_dir / "psd.py"
        
        if not custom_psd_path.exists():
            log_message(f"Custom psd.py not found at: {custom_psd_path}", "warning")
            return False
        
        # 2) Import the live nukescripts.psd module (if not already imported)
        try:
            live_psd = importlib.import_module('nukescripts.psd')
        except ImportError as e:
            log_message(f"Failed to import nukescripts.psd: {e}", "error")
            return False
        
        # 3) Load our custom psd.py module
        spec = importlib.util.spec_from_file_location("TL_BreakOutPSD.psd", str(custom_psd_path))
        if not spec or not spec.loader:
            log_message("Failed to create module spec", "error")
            return False
            
        custom_mod = importlib.util.module_from_spec(spec)
        
        # Add to sys.modules to ensure it's properly loaded
        sys.modules["TL_BreakOutPSD.psd"] = custom_mod
        
        # Execute the custom module
        spec.loader.exec_module(custom_mod)
        
        # 4) Verify all required functions exist in our custom module
        required_functions = ['getLayers', 'breakoutLayers', 'BreakoutThreadClass', 'doReaderBreakout']
        missing_functions = []
        
        for func_name in required_functions:
            if not hasattr(custom_mod, func_name):
                missing_functions.append(func_name)
        
        if missing_functions:
            log_message(f"Custom module missing functions: {missing_functions}", "error")
            return False
        
        # 5) Patch the live module in-place (preserves existing references)
        live_psd.getLayers = custom_mod.getLayers
        live_psd.breakoutLayers = custom_mod.breakoutLayers
        live_psd.BreakoutThreadClass = custom_mod.BreakoutThreadClass
        live_psd.doReaderBreakout = custom_mod.doReaderBreakout
        
        # 6) Verify the patch worked by checking if our enhanced function is active
        if hasattr(live_psd.doReaderBreakout, '__doc__') and 'Photoshop' in str(live_psd.doReaderBreakout.__doc__):
            log_message("✅ Successfully patched nukescripts.psd with TL_BreakOutPSD version", "info")
            log_message("Enhanced PSD breakout now includes Photoshop editing option", "info")
            return True
        else:
            log_message("⚠️ Patch applied but verification failed", "warning")
            return False
            
    except Exception as e:
        log_message(f"❌ ERROR while patching nukescripts.psd: {e}", "error")
        return False

# Execute the patching
log_message("Initializing TL_BreakOutPSD toolchain...", "info")
import time
start_time = time.time()

patch_result = patch_nukescripts_psd()

# Log timing and result
elapsed_time = time.time() - start_time
if patch_result:
    log_message(f"TL_BreakOutPSD initialized successfully in {elapsed_time:.3f}s", "info")
else:
    log_message(f"TL_BreakOutPSD initialization failed after {elapsed_time:.3f}s", "warning")

# Log performance metrics if available
if LOGGING_AVAILABLE:
    try:
        try:
            from utils.PipelineLogger import log_performance
        except ImportError:
            from PipelineLogger import log_performance
            
        log_performance("TL_BreakOutPSD_initialization", elapsed_time, {
            "patch_successful": patch_result,
            "logging_available": LOGGING_AVAILABLE
        })
    except ImportError:
        pass  # Performance logging not available
    except Exception:
        pass  # Silent fallback for performance logging errors

# Optional: Add a menu command to re-patch if needed during development
def reapply_psd_patch():
    """Menu command to re-apply the PSD patch (useful for development)"""
    log_message("Re-applying PSD patch...", "info")
    success = patch_nukescripts_psd()
    if success:
        nuke.message("PSD patch re-applied successfully!")
        log_message("PSD patch re-applied successfully via menu command", "info")
    else:
        nuke.message("Failed to re-apply PSD patch. Check Script Editor for details.")
        log_message("Failed to re-apply PSD patch via menu command", "error")

# Add to Nuke menu for easy access during development
try:
    import nukescripts
    nukescripts.register_python_script("Re-apply PSD Patch", "TL_BreakOutPSD.init.reapply_psd_patch()")
except:
    pass  # Menu registration is optional

# --- end patch ---
