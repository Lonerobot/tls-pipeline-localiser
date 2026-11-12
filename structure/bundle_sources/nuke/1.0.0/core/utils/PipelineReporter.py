"""
Pipeline reporting utilities for clean console output
"""

import time
import os
from pathlib import Path


class PipelineReporter:
    """
    Utility class for generating clean, formatted console reports
    """
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.toolchain_data = []
        self.start_time = time.time()
        self.env_data = {}
        
    def add_toolchain(self, name, version, enabled, load_time, build_menu=False, build_toolbar=False):
        """Add toolchain data for reporting"""
        self.toolchain_data.append({
            'name': name,
            'version': version,
            'enabled': enabled,
            'load_time': load_time,
            'build_menu': build_menu,
            'build_toolbar': build_toolbar
        })
    
    def set_environment_data(self, env_data):
        """Set environment data for reporting"""
        self.env_data = env_data
    
    def print_initialization_header(self, custom_logo=None):
        """Print the main header for pipeline initialization"""
        if custom_logo:
            print(custom_logo)
        else:
            # Use The Line's ASCII art style but with cleaner formatting for production
            header = r"""
  _____ _  _ ___   _	___ _  _ ___			
 |_   _| || | __| | |  |_ _| \| | __|   		
_______________________________________          
   |_| |_||_|___| |____|___|_|\_|___|   		
                                                
    _   _  _ ___ __  __   _ _____ ___ ___  _  _ 
   /_\ | \| |_ _|  \/  | /_\_   _|_ _/ _ \| \| |
  / _ \| .` || || |\/| |/ _ \| |  | | (_) | .` |
 /_/ \_\_|\_|___|_|  |_/_/ \_\_| |___\___/|_|\_|
 
INITIALIZING THE LINE NUKE PIPELINE...
"""
            print(header)
    
    def print_environment_summary(self):
        """Print environment variables summary"""
        if not self.debug_mode:
            # Minimal output for production
            pass  # Skip environment details in production mode
    
    def print_toolchains_summary(self):
        """Print clean toolchains summary table"""
        if not self.toolchain_data:
            print("[  No toolchains configured  ]")
            return
            
        if not self.debug_mode:
            self._print_clean_table()
        else:
            self._print_debug_table()
    
    def _print_clean_table(self):
        """Print clean, production-ready table"""
        # Header
        print("[  Loading Toolchains  ]")
        
        # Calculate column widths
        max_name = max(len(tc['name']) for tc in self.toolchain_data)
        max_version = max(len(tc['version']) for tc in self.toolchain_data)
        name_width = max(12, max_name + 2)
        version_width = max(8, max_version + 2)
        
        # Table header with separate Menu and Toolbar columns
        separator = f"{'─' * name_width}┼{'─' * version_width}┼─────────┼─────────┼──────┼───────────┼─────────"
        header = f"{'Toolchain':<{name_width}}│{'Version':<{version_width}}│ Status  │Load Time│ Menu │ Toolbar   │ Total"
        
        print(separator)
        print(header)
        print(separator)
        
        # Table rows
        total_time = 0
        enabled_count = 0
        
        for tc in self.toolchain_data:
            status = "OK " if tc['enabled'] else "OFF"
            load_time = f"{tc['load_time']:.3f}" if tc['enabled'] else "N/A"
            
            # Separate menu and toolbar indicators using clear ON/OFF text
            if tc['enabled']:
                menu_indicator = "ON" if tc['build_menu'] else "OFF"
                toolbar_indicator = "ON" if tc['build_toolbar'] else "OFF"
            else:
                menu_indicator = "N/A"
                toolbar_indicator = "N/A"
                
            total = f"{tc['load_time']:.3f}" if tc['enabled'] else "0.000"
            
            row = f"{tc['name']:<{name_width}}│{tc['version']:<{version_width}}│{status:<9}│{load_time:<9}│{menu_indicator:<6}│{toolbar_indicator:<11}│{total}"
            print(row)
            
            if tc['enabled']:
                total_time += tc['load_time']
                enabled_count += 1
        
        # Footer
        print(separator)
        total_time_str = f"{total_time:.3f}"
        footer = f"{'Total':<{name_width}}│{f'({enabled_count})':<{version_width}}│{'READY':<9}│{total_time_str:<9}│{'─':<6}│{'─':<11}│{total_time:.3f}"
        print(footer)
        print(f"[  Pipeline Ready - {enabled_count} toolchains loaded in {total_time:.3f}s  ]")
    
    def _print_debug_table(self):
        """Print detailed debug table"""
        # This is the existing debug output - keep it detailed
        print("=== TOOLCHAINS DEBUG REPORT ===")
        for tc in self.toolchain_data:
            print(f"Toolchain: {tc['name']}")
            print(f"  Version: {tc['version']}")
            print(f"  Enabled: {tc['enabled']}")
            print(f"  Load Time: {tc['load_time']:.4f}s")
            print(f"  Build Menu: {tc['build_menu']}")
            print(f"  Build Toolbar: {tc['build_toolbar']}")
            print()
    
    def print_completion_footer(self):
        """Print completion message"""
        total_time = time.time() - self.start_time
        if not self.debug_mode:
            print(f"[  Pipeline Ready ({total_time:.3f}s)  ]")
        else:
            print(f"=== PIPELINE INITIALIZATION COMPLETE ({total_time:.3f}s) ===")


def create_reporter(debug_mode=False):
    """Create a new pipeline reporter instance"""
    return PipelineReporter(debug_mode)
