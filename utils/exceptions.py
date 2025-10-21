"""
Sniper-IT Agent - Custom Exceptions
Hierarchy of custom exceptions for better error handling
"""


class SniperITException(Exception):
    """Base exception for all Sniper-IT Agent errors"""
    pass


class ConfigurationError(SniperITException):
    """Configuration-related errors (missing config, invalid format, etc.)"""
    pass


class APIError(SniperITException):
    """General API errors"""
    pass


class APIConnectionError(APIError):
    """API connection and communication errors"""
    pass


class APIAuthenticationError(APIConnectionError):
    """API authentication failures (invalid API key, etc.)"""
    pass


class DataCollectionError(SniperITException):
    """Data collection errors (OS commands failed, etc.)"""
    pass


class ValidationError(SniperITException):
    """Validation errors (invalid input, etc.)"""
    pass


class SetupError(SniperITException):
    """Setup wizard errors"""
    pass
