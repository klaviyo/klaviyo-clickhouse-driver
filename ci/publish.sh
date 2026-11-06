#!/usr/bin/env bash
# Uploads ./wheelhouse to Artifactory's pypi-local, the same way chariot's
# pipeline does. Artifactory versions are immutable and re-uploading one
# returns 403, so this only publishes when the merge changed LOCAL_VERSION.
set -euo pipefail

if ! git diff HEAD~1 HEAD -- clickhouse_driver/__init__.py | grep -q '^+LOCAL_VERSION'; then
  echo "LOCAL_VERSION unchanged in this merge; not publishing."
  exit 0
fi

ls -l wheelhouse

echo "$JFROG_ARTIFACTORY_JENKINS_PYPIRC_FILE_SECRET" | base64 --decode > ~/.pypirc
python -m pip install --quiet twine
python -m twine upload --non-interactive -r local wheelhouse/*
