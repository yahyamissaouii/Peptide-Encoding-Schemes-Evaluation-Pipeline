"""
Simple runner script for the Peptide Encoding Research Platform

This script launches the Streamlit application with optimal settings.
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Launch the Streamlit application"""

    # Get the path to the app
    app_path = Path(__file__).parent / "app.py"

    # Check if app exists
    if not app_path.exists():
        print(f"Error: Could not find app.py at {app_path}")
        sys.exit(1)

    print("Starting Peptide Encoding Research Platform...")
    print(f"App location: {app_path}")
    print("🌐 Opening browser at http://localhost:8501")
    print("\n" + "="*60)
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")

    # Run streamlit
    try:
        subprocess.run([
            "streamlit", "run", str(app_path),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ])
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
    except FileNotFoundError:
        print("\n❌ Error: Streamlit is not installed or not in PATH")
        print("Please install it with: pip install streamlit")
        sys.exit(1)

if __name__ == "__main__":
    main()