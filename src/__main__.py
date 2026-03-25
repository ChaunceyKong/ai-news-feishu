"""允许通过 python -m src 运行"""

from .main import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
