# Centralized version management for Trade Nothing

__version__ = "0.9.3"

def check_version_consistency():
    """Verify that all files in the repository contain consistent version numbers.
    Used in CI/CD and Makefile checks.
    """
    import os
    import re

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_version = f"v{__version__}"

    # Files to check and their expected match patterns
    checks = [
        {
            "file": "SKILL.md",
            "regex": r"Trade Nothing v\d+\.\d+(?:\.\d+)?",
            "expected": f"Trade Nothing {target_version}"
        },
        {
            "file": "Makefile",
            "regex": r"Trade Nothing v\d+\.\d+(?:\.\d+)?",
            "expected": f"Trade Nothing {target_version}"
        },
        {
            "file": "CONTRIBUTING.md",
            "regex": r"v\d+\.\d+(?:\.\d+)?",
            "expected": target_version
        }
    ]

    mismatches = []

    for check in checks:
        file_path = os.path.join(base_dir, check["file"])
        if not os.path.exists(file_path):
            print(f"[WARN] Version checker: File not found: {check['file']}")
            continue

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        matches = re.findall(check["regex"], content)
        for match in matches:
            if match != check["expected"]:
                mismatches.append((check["file"], match, check["expected"]))

    if mismatches:
        print("❌ [ERROR] Version inconsistencies detected in the workspace:")
        for file_name, found, expected in mismatches:
            print(f"   - {file_name}: Found '{found}', but expected '{expected}'")
        raise ValueError("Version inconsistency check failed!")
    else:
        print("✅ [SUCCESS] Version consistency check passed.")

if __name__ == "__main__":
    check_version_consistency()
