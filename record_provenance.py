"""Record provenance information (image digests and timestamp) for assessment results."""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomli
except ImportError:
    try:
        import tomllib as tomli
    except ImportError:
        print("Error: tomli required. Install with: pip install tomli")
        sys.exit(1)


def get_image_digest(image: str) -> str:
    """Get the immutable digest for a docker image.

    Returns the RepoDigest (sha256:...) if available, otherwise falls back to the image ID.
    """
    try:
        # Try to get RepoDigest first (for pulled images)
        result = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{index .RepoDigests 0}}"],
            capture_output=True,
            text=True,
            check=True
        )
        digest = result.stdout.strip()
        if digest:
            return digest
    except subprocess.CalledProcessError:
        pass

    # Fallback to image ID for local builds
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return f"unknown:{image}"


def parse_scenario(scenario_path: Path) -> dict:
    """Parse scenario.toml and extract image information."""
    toml_data = scenario_path.read_text()
    return tomli.loads(toml_data)


def collect_image_digests(scenario: dict) -> dict[str, str]:
    """Collect digests for all images in the scenario."""
    digests = {}

    # Green agent
    green_image = scenario["green_agent"]["image"]
    digests["green_agent"] = get_image_digest(green_image)

    # Participants
    for participant in scenario.get("participants", []):
        name = participant["name"]
        image = participant["image"]
        if image:  # Skip if image is empty
            digests[name] = get_image_digest(image)

    return digests


def write_provenance(output_path: Path, image_digests: dict[str, str]) -> None:
    """Write provenance information to a JSON file."""
    provenance = {
        "image_digests": image_digests,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    }

    with open(output_path, "w") as f:
        json.dump(provenance, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Record provenance information for assessment results")
    parser.add_argument("--scenario", type=Path, required=True, help="Path to scenario.toml")
    parser.add_argument("--output", type=Path, required=True, help="Path to output provenance JSON file")
    args = parser.parse_args()

    if not args.scenario.exists():
        print(f"Error: {args.scenario} not found")
        sys.exit(1)

    scenario = parse_scenario(args.scenario)
    image_digests = collect_image_digests(scenario)
    write_provenance(args.output, image_digests)

    print(f"Recorded provenance to {args.output} ({len(image_digests)} images)")


if __name__ == "__main__":
    main()
