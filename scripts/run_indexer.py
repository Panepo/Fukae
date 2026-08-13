#!/usr/bin/env python3
"""Command-line script to execute the DocumentIndexer."""

import argparse
import json
import sys
from pathlib import Path

# Add the project root to the path so we can import from core and indexer
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexer.indexer import DocumentIndexer, _PASSTHROUGH_EXTENSIONS, _PIPELINE_EXTENSIONS


def main():
    parser = argparse.ArgumentParser(
        description="Index documents using the DocumentIndexer pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        help="Path to a document file or directory to index",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Path to the output folder for indexed chunk JSON files",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Recursively index all documents in a directory",
    )

    args = parser.parse_args()

    # Validate input path
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input path '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Validate and create output folder
    output_folder = Path(args.output)
    if not output_folder.is_dir():
        try:
            output_folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error: Cannot create output folder '{args.output}': {e}", file=sys.stderr)
            sys.exit(1)

    # Initialize indexer
    print(f"Initializing DocumentIndexer for: {args.input}")
    indexer = DocumentIndexer()

    all_exts = _PASSTHROUGH_EXTENSIONS | _PIPELINE_EXTENSIONS

    # Process input
    try:
        if input_path.is_file():
            print(f"Processing file: {input_path.name}")
            embedded_data = indexer.load(str(input_path))

            # Output results in reference.json format
            output_filename = f"{input_path.stem}_chunks.json"
            output_path = output_folder / output_filename

            # embedded_data is now a dict with 'model', 'dimension', 'device', 'doc_stem', 'chunks'
            # Write the embedded data structure in reference.json format
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(embedded_data, f, indent=2, ensure_ascii=False)
            print(f"Chunks saved to: {output_path} ({len(embedded_data.get('chunks', []))} chunks)")

        elif input_path.is_dir():
            print(f"Processing directory: {input_path}")
            pattern = "**/*" if args.recursive else "*"
            files_to_process = sorted(input_path.glob(pattern))
            files_to_process = [p for p in files_to_process if p.is_file() and p.suffix.lower() in all_exts]

            if not files_to_process:
                print("No supported documents found in the directory.", file=sys.stderr)
                sys.exit(1)

            for file_path in files_to_process:
                print(f"Processing file: {file_path.name}")
                embedded_data = indexer.load(str(file_path))

                # Output results in reference.json format
                output_filename = f"{file_path.stem}_chunks.json"
                output_path = output_folder / output_filename

                # embedded_data is now a dict with 'model', 'dimension', 'device', 'doc_stem', 'chunks'
                # Write the embedded data structure in reference.json format
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(embedded_data, f, indent=2, ensure_ascii=False)
                print(f"  -> Chunks saved to: {output_path} ({len(embedded_data.get('chunks', []))} chunks)")

        else:
            print(f"Error: Input path '{args.input}' is neither a file nor a directory.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error during indexing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
