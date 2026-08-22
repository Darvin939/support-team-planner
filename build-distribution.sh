#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: ./build-distribution.sh [--output PATH]

Build the production frontend and create a Linux application distribution
directory and ZIP archive.

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

runtime_files=(
    "support_planner.py"
    "access_control.py"
    "api_models.py"
    "auth.py"
    "query_parsing.py"
    "ssl_context.py"
    "task_dependency_rules.py"
    "task_rules.py"
    "utils.py"
    "requirements.txt"
    "run.sh"
    "check.sh"
)

runtime_patterns=(
    "db/*.py"
    "routers/*.py"
)

for relative_path in "${runtime_files[@]}"; do
    if [[ ! -e "$script_dir/$relative_path" ]]; then
        echo "Error: required source is missing: $relative_path" >&2
        exit 1
    fi
done

for pattern in "${runtime_patterns[@]}"; do
    if ! compgen -G "$script_dir/$pattern" >/dev/null; then
        echo "Error: required sources are missing: $pattern" >&2
        exit 1
    fi
done

command -v npm >/dev/null 2>&1 || {
    echo "Error: npm is required to build the frontend." >&2
    exit 1
}
command -v zip >/dev/null 2>&1 || {
    echo "Error: zip is required to create the distribution archive." >&2
    exit 1
}

echo "Building production frontend..."
(cd "$script_dir/frontend" && npm run build)

if [[ ! -f "$script_dir/frontend/dist/index.html" ]]; then
    echo "Error: frontend build did not create frontend/dist/index.html." >&2
    exit 1
fi
if [[ ! -f "$script_dir/frontend/dist/taskTransitions.json" ]]; then
    echo "Error: frontend build did not create frontend/dist/taskTransitions.json." >&2
    exit 1
fi

output_parent="$(dirname -- "$output_path")"
output_name="$(basename -- "$output_path")"
archive_path="${output_path}.zip"
if [[ -d "$archive_path" ]]; then
    echo "Error: archive path is a directory: $archive_path" >&2
    exit 2
fi
mkdir -p -- "$output_parent"
staging_dir="$(mktemp -d -- "$output_parent/.${output_name}.staging.XXXXXX")"
archive_staging_dir=""

cleanup() {
    if [[ -n "${staging_dir:-}" && -d "$staging_dir" ]]; then
        rm -rf -- "$staging_dir"
    fi
    if [[ -n "${archive_staging_dir:-}" && -d "$archive_staging_dir" ]]; then
        rm -rf -- "$archive_staging_dir"
    fi
}
trap cleanup EXIT

for relative_path in "${runtime_files[@]}"; do
    destination="$staging_dir/$relative_path"
    mkdir -p -- "$(dirname -- "$destination")"
    cp -- "$script_dir/$relative_path" "$destination"
done

for pattern in "${runtime_patterns[@]}"; do
    for source_path in "$script_dir"/$pattern; do
        relative_path="${source_path#"$script_dir/"}"
        destination="$staging_dir/$relative_path"
        mkdir -p -- "$(dirname -- "$destination")"
        cp -- "$source_path" "$destination"
    done
done

mkdir -p -- "$staging_dir/frontend"
cp -R -- "$script_dir/frontend/dist" "$staging_dir/frontend/dist"
chmod +x "$staging_dir/run.sh" "$staging_dir/check.sh"

if [[ -e "$output_path" ]]; then
    rm -rf -- "$output_path"
fi
mv -- "$staging_dir" "$output_path"
staging_dir=""

archive_staging_dir="$(mktemp -d -- "$output_parent/.${output_name}.archive.XXXXXX")"
(cd "$output_path" && zip -qr "$archive_staging_dir/$output_name.zip" .)
mv -f -- "$archive_staging_dir/$output_name.zip" "$archive_path"
rm -rf -- "$archive_staging_dir"
archive_staging_dir=""

echo "Distribution created: $output_path"
echo "Distribution archive created: $archive_path"
