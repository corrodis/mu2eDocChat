from pathlib import Path
import os

def get_data_dir():
    """Get the data directory for docdb storage, creating it if necessary."""
    # First priroty is the environment variable
    data_dir = os.getenv('MU2E_DATA_DIR')
    if data_dir:
        return Path(data_dir)

    # If not set, use default in home directory
    default_dir = Path.home() / '.mu2e' / 'data'
    
    if not default_dir.exists():
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created default data directory at {default_dir}")
            print("You can override this location by setting MU2E_DATA_DIR environment variable")
        except Exception as e:
            raise RuntimeError(
                "Could not find or create data directory. "
                "Please either:\n"
                "1. Set MU2E_DATA_DIR environment variable\n"
                "2. Ensure ~/.mu2e/data can be created\n"
                f"Error: {str(e)}"
            )
    
    return default_dir
