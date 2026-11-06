#!/usr/bin/env bash
# Builds the wheels and sdist that segmentation-service installs from Artifactory.
#
# Usage: ci/build_wheels.sh <platform> [<arch>]
#   ci/build_wheels.sh linux x86_64
#   ci/build_wheels.sh linux aarch64
#   ci/build_wheels.sh sdist
#
# Output goes to ./wheelhouse. Linux builds need Docker; cibuildwheel runs them
# inside manylinux containers. There is no macOS wheel: macOS installs build
# from the sdist, which ships the generated .c files, with Xcode's compiler.
set -euo pipefail

CIBUILDWHEEL_VERSION="2.23.3"
PYTHON_BUILD="cp310"

platform="${1:?platform required: linux or sdist}"
arch="${2:-}"

python -m pip install --quiet --upgrade pip

if [[ "$platform" == "sdist" ]]; then
  # Cython must be installed so the sdist ships generated .c files and
  # installs without Cython.
  python -m pip install --quiet build cython
  python -m build --sdist --outdir wheelhouse
  exit 0
fi

python -m pip install --quiet "cibuildwheel==${CIBUILDWHEEL_VERSION}"

case "$platform" in
  linux)
    export CIBW_BUILD="${PYTHON_BUILD}-manylinux_*"
    export CIBW_ARCHS_LINUX="${arch:?arch required for linux: x86_64 or aarch64}"
    ;;
  *)
    echo "unknown platform: $platform" >&2
    exit 1
    ;;
esac

export CIBW_BEFORE_BUILD="pip install cython"
# Import the built wheel as a smoke test, from outside the source tree so the
# installed package is what gets imported.
export CIBW_TEST_COMMAND="python -c \"import clickhouse_driver, clickhouse_driver.varint, clickhouse_driver.bufferedreader; print(clickhouse_driver.__version__)\""

python -m cibuildwheel --platform "$platform" --output-dir wheelhouse
