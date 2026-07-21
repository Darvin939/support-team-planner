#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: ./build-distribution.sh [--output PATH]

Build the production frontend and create a Linux application distribution.

Options:
  --output PATH  Distribution directory (default: build/support-team-planner)
  -h, --help     Show this help
EOF
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
output_path="build/support-team-planner"

while (($#)); do
    case "$1" in
        --output)
            if (($# < 2)) || [[ -z "$2" ]]; then
                echo "Error: --output requires a path." >&2
                exit 2
            fi
            output_path="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "$output_path" != /* ]]; then
    output_path="$script_dir/$output_path"
fi
output_path="$(realpath -m -- "$output_path")"

if [[ "$output_path" == "/" || "$output_path" == "$script_dir" ]]; then
    echo "Error: refusing unsafe output directory: $output_path" >&2
    exit 2
fi

required_sources=(
    "support_planner.py"
    "auth.py"
    "ssl_context.py"
    "utils.py"
    "requirements.txt"
    "run.sh"
    "check.sh"
    "db"
    "frontend/src/data/taskTransitions.json"
)

for relative_path in "${required_sources[@]}"; do
    if [[ ! -e "$script_dir/$relative_path" ]]; then
        echo "Error: required source is missing: $relative_path" >&2
        exit 1
    fi
done

command -v npm >/dev/null 2>&1 || {
    echo "Error: npm is required to build the frontend." >&2
    exit 1
}

echo "Building production frontend..."
(cd "$script_dir/frontend" && npm run build)

if [[ ! -f "$script_dir/frontend/dist/index.html" ]]; then
    echo "Error: frontend build did not create frontend/dist/index.html." >&2
    exit 1
fi

output_parent="$(dirname -- "$output_path")"
output_name="$(basename -- "$output_path")"
mkdir -p -- "$output_parent"
staging_dir="$(mktemp -d -- "$output_parent/.${output_name}.staging.XXXXXX")"

cleanup() {
    if [[ -n "${staging_dir:-}" && -d "$staging_dir" ]]; then
        rm -rf -- "$staging_dir"
    fi
}
trap cleanup EXIT

for relative_path in \
    support_planner.py auth.py ssl_context.py utils.py requirements.txt run.sh check.sh; do
    cp -- "$script_dir/$relative_path" "$staging_dir/$relative_path"
done

cp -R -- "$script_dir/db" "$staging_dir/db"
mkdir -p -- "$staging_dir/frontend/src/data"
cp -R -- "$script_dir/frontend/dist" "$staging_dir/frontend/dist"
cp -- "$script_dir/frontend/src/data/taskTransitions.json" \
    "$staging_dir/frontend/src/data/taskTransitions.json"
chmod +x "$staging_dir/run.sh" "$staging_dir/check.sh"

required_outputs=(
    "support_planner.py"
    "requirements.txt"
    "db/__init__.py"
    "frontend/dist/index.html"
    "frontend/src/data/taskTransitions.json"
)
for relative_path in "${required_outputs[@]}"; do
    if [[ ! -e "$staging_dir/$relative_path" ]]; then
        echo "Error: distribution is incomplete: $relative_path" >&2
        exit 1
    fi
done

if [[ -e "$output_path" ]]; then
    rm -rf -- "$output_path"
fi
mv -- "$staging_dir" "$output_path"
staging_dir=""

echo "Distribution created: $output_path"
