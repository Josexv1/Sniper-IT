"""
Sniper-IT Agent - CLI Formatters
Beautiful terminal output using rich library
"""

from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.spinner import Spinner
from rich.live import Live
from core.constants import STATUS_OK, STATUS_ERROR, STATUS_WARNING, STATUS_INFO, STATUS_QUESTION


# Global console instance
console = Console()


def print_header(text: str) -> None:
    """Print a section header"""
    console.print(f"\n{'═' * 70}", style="cyan")
    console.print(f"  {text}", style="bold cyan")
    console.print(f"{'═' * 70}", style="cyan")


def print_ok(text: str) -> None:
    """Print success message"""
    console.print(f"{STATUS_OK} {text}", style="green")


def print_error(text: str) -> None:
    """Print error message"""
    console.print(f"{STATUS_ERROR} {text}", style="bold red")


def print_warning(text: str) -> None:
    """Print warning message"""
    console.print(f"{STATUS_WARNING} {text}", style="yellow")


def print_info(text: str) -> None:
    """Print info message"""
    console.print(f"{STATUS_INFO} {text}", style="blue")


def print_question(text: str) -> None:
    """Print question/prompt message"""
    console.print(f"{STATUS_QUESTION} {text}", style="cyan")


def create_table(title: str, columns: List[str], rows: List[List[str]]) -> Table:
    """
    Create a rich table
    
    Args:
        title: Table title
        columns: List of column headers
        rows: List of rows (each row is a list of values)
        
    Returns:
        Rich Table object
    """
    table = Table(title=title, show_header=True, header_style="bold magenta")
    
    # Add columns
    for column in columns:
        table.add_column(column)
    
    # Add rows
    for row in rows:
        table.add_row(*[str(val) for val in row])
    
    return table


def display_table(title: str, columns: List[str], rows: List[List[str]]) -> None:
    """
    Display a table to console
    
    Args:
        title: Table title
        columns: List of column headers
        rows: List of rows (each row is a list of values)
    """
    table = create_table(title, columns, rows)
    console.print(table)


def display_companies_table(companies: List[Dict[str, Any]]) -> None:
    """
    Display companies in a formatted table
    
    Args:
        companies: List of company dictionaries from API
    """
    if not companies:
        print_warning("No companies found")
        return
    
    rows = []
    for company in companies:
        company_id = company.get('id', 'N/A')
        name = company.get('name', 'N/A')
        assets_count = company.get('assets_count', 0)
        rows.append([str(company_id), name, str(assets_count)])
    
    display_table(
        title="Available Companies",
        columns=["ID", "Company Name", "Assets"],
        rows=rows
    )


def display_categories_table(categories: List[Dict[str, Any]]) -> None:
    """
    Display categories in a formatted table
    
    Args:
        categories: List of category dictionaries from API
    """
    if not categories:
        print_warning("No categories found")
        return
    
    rows = []
    for category in categories:
        category_id = category.get('id', 'N/A')
        name = category.get('name', 'N/A')
        item_count = category.get('item_count', category.get('assets_count', 0))
        rows.append([str(category_id), name, str(item_count)])
    
    display_table(
        title="Available Categories",
        columns=["ID", "Category Name", "Item Count"],
        rows=rows
    )


def display_fieldsets_table(fieldsets: List[Dict[str, Any]]) -> None:
    """
    Display fieldsets in a formatted table
    
    Args:
        fieldsets: List of fieldset dictionaries from API
    """
    if not fieldsets:
        print_warning("No fieldsets found")
        return
    
    rows = []
    for fieldset in fieldsets:
        fieldset_id = fieldset.get('id', 'N/A')
        name = fieldset.get('name', 'N/A')
        fields_count = len(fieldset.get('fields', {}).get('rows', []))
        rows.append([str(fieldset_id), name, str(fields_count)])
    
    display_table(
        title="Available Fieldsets",
        columns=["ID", "Fieldset Name", "Fields"],
        rows=rows
    )


def display_status_list(statuses: List[Dict[str, Any]]) -> None:
    """
    Display status labels in a formatted table
    
    Args:
        statuses: List of status dictionaries from API
    """
    if not statuses:
        print_warning("No statuses found")
        return
    
    rows = []
    for status in statuses:
        status_id = status.get('id', 'N/A')
        name = status.get('name', 'N/A')
        status_type = status.get('type', 'N/A')
        rows.append([str(status_id), name, status_type])
    
    display_table(
        title="Available Status Labels",
        columns=["ID", "Status Name", "Type"],
        rows=rows
    )


def display_custom_fields_table(fields: List[Dict[str, Any]], validation: Optional[Dict[str, str]] = None) -> None:
    """
    Display custom fields in a formatted table with optional validation status
    
    Args:
        fields: List of custom field dictionaries from API
        validation: Optional dict mapping db_column to validation status
    """
    if not fields:
        print_warning("No custom fields found")
        return
    
    rows = []
    for field in fields:
        field_id = field.get('id', 'N/A')
        name = field.get('name', 'N/A')
        db_column = field.get('db_column_name', 'N/A')
        field_type = field.get('type', field.get('format', 'N/A'))
        
        if validation and db_column in validation:
            status = validation[db_column]
            rows.append([str(field_id), name, db_column, field_type, status])
        else:
            rows.append([str(field_id), name, db_column, field_type])
    
    if validation:
        display_table(
            title="Custom Fields Validation",
            columns=["ID", "Field Name", "DB Column", "Format", "Status"],
            rows=rows
        )
    else:
        display_table(
            title="Custom Fields in Snipe-IT",
            columns=["ID", "Field Name", "DB Column", "Format"],
            rows=rows
        )


def prompt_input(prompt: str, default: Optional[str] = None) -> str:
    """
    Prompt user for input
    
    Args:
        prompt: Prompt text
        default: Default value if user presses Enter
        
    Returns:
        User input string
    """
    if default:
        prompt_text = f"{STATUS_INFO} {prompt} [{default}]: "
    else:
        prompt_text = f"{STATUS_INFO} {prompt}: "
    
    return console.input(prompt_text).strip() or (default if default else "")


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """
    Prompt user for yes/no answer
    
    Args:
        prompt: Prompt text
        default: Default value (True for Yes, False for No)
        
    Returns:
        Boolean response
    """
    default_str = "Y/n" if default else "y/N"
    response = console.input(f"{STATUS_QUESTION} {prompt} [{default_str}]: ").strip().lower()
    
    if not response:
        return default
    
    return response in ['y', 'yes']


def display_panel(content: str, title: str = "", border_style: str = "blue") -> None:
    """
    Display content in a panel
    
    Args:
        content: Panel content
        title: Panel title
        border_style: Border color style
    """
    panel = Panel(content, title=title, border_style=border_style)
    console.print(panel)


def print_success_summary(message: str) -> None:
    """
    Print a success summary panel
    
    Args:
        message: Success message
    """
    display_panel(f"[green]{message}[/green]", title="Success", border_style="green")


def print_error_summary(message: str) -> None:
    """
    Print an error summary panel
    
    Args:
        message: Error message
    """
    display_panel(f"[red]{message}[/red]", title="Error", border_style="red")


@contextmanager
def spinner(text: str = "Loading...", spinner_style: str = "dots"):
    """
    Context manager for displaying a spinner during operations
    
    Args:
        text: Text to display next to spinner
        spinner_style: Spinner style (dots, line, arc, etc.)
        
    Usage:
        with spinner("Collecting data..."):
            # Do work here
            pass
    """
    with Live(Spinner(spinner_style, text=text, style="cyan"), console=console, refresh_per_second=10):
        yield
