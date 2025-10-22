"""
Sniper-IT Agent - Logging System
Handles verbosity levels and file logging
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from rich.console import Console


class Logger:
    """Custom logger with verbosity levels and file output"""
    
    LEVEL_QUIET = 0      # Only show critical info (default)
    LEVEL_VERBOSE = 1    # Show all text (-v)
    LEVEL_DEBUG = 2      # Show debug data (-vv)
    
    def __init__(self, verbosity: int = 0, log_file: Optional[str] = None):
        """
        Initialize logger
        
        Args:
            verbosity: Verbosity level (0=quiet, 1=verbose, 2=debug)
            log_file: Path to log file if logging to file
        """
        self.verbosity = verbosity
        self.log_file = log_file
        self.console = Console()
        self.file_handle = None
        
        # Open log file if specified
        if self.log_file:
            try:
                self.file_handle = open(self.log_file, 'w', encoding='utf-8')
                self._write_to_file(f"=== Sniper-IT Agent Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            except Exception as e:
                self.console.print(f"[yellow]⚠ Warning: Could not open log file: {e}[/yellow]")
                self.file_handle = None
    
    def _write_to_file(self, message: str) -> None:
        """Write message to log file"""
        if self.file_handle:
            try:
                # Remove rich markup for file output
                clean_message = message
                # Basic cleanup of rich markup
                for tag in ['[bold]', '[/bold]', '[cyan]', '[/cyan]', '[green]', '[/green]', 
                           '[red]', '[/red]', '[yellow]', '[/yellow]', '[blue]', '[/blue]',
                           '[bold cyan]', '[/bold cyan]', '[bold red]', '[/bold red]']:
                    clean_message = clean_message.replace(tag, '')
                
                self.file_handle.write(clean_message)
                if not clean_message.endswith('\n'):
                    self.file_handle.write('\n')
                self.file_handle.flush()
            except Exception:
                pass  # Silently fail file writes
    
    def quiet(self, message: str, **kwargs) -> None:
        """Always show (LEVEL_QUIET and above)"""
        self.console.print(message, **kwargs)
        self._write_to_file(message)
    
    def verbose(self, message: str, **kwargs) -> None:
        """Show when -v or -vv is used (LEVEL_VERBOSE and above)"""
        if self.verbosity >= self.LEVEL_VERBOSE:
            self.console.print(message, **kwargs)
        self._write_to_file(message)
    
    def debug(self, message: str, **kwargs) -> None:
        """Show only when -vv is used (LEVEL_DEBUG)"""
        if self.verbosity >= self.LEVEL_DEBUG:
            self.console.print(message, **kwargs)
        self._write_to_file(message)
    
    def input(self, prompt: str) -> str:
        """Get user input"""
        response = self.console.input(prompt)
        self._write_to_file(f"{prompt}{response}")
        return response
    
    def close(self) -> None:
        """Close log file if open"""
        if self.file_handle:
            try:
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None


# Global logger instance
_global_logger: Optional[Logger] = None


def init_logger(verbosity: int = 0, log_file: Optional[str] = None) -> Logger:
    """
    Initialize global logger
    
    Args:
        verbosity: Verbosity level (0=quiet, 1=verbose, 2=debug)
        log_file: Path to log file if logging to file
        
    Returns:
        Logger instance
    """
    global _global_logger
    _global_logger = Logger(verbosity, log_file)
    return _global_logger


def get_logger() -> Logger:
    """
    Get global logger instance
    
    Returns:
        Logger instance (creates default if not initialized)
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger()
    return _global_logger


def close_logger() -> None:
    """Close global logger"""
    global _global_logger
    if _global_logger:
        _global_logger.close()
        _global_logger = None
