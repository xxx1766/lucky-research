"""Entry point so ``python -m research_assistant.migrate ...`` works."""
from research_assistant.migrate.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
