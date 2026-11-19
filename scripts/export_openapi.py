import argparse
import json
from pathlib import Path

from apps.api.application import create_app
from apps.api.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description='Export the MeetingIntel HTTP contract.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    schema = create_app(Settings()).openapi()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
