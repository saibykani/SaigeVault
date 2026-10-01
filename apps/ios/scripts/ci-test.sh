#!/usr/bin/env bash
# Generate the Xcode project and run unit + UI tests on the newest available
# iPhone simulator. Used by CI; works locally on any Mac with Xcode.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v xcodegen >/dev/null || brew install xcodegen
xcodegen generate

DEVICE_ID=$(xcrun simctl list devices available --json | python3 -c '
import json, sys
devices = json.load(sys.stdin)["devices"]
ios = sorted((k for k in devices if "iOS" in k), key=lambda k: [int(p) for p in k.rsplit("iOS-", 1)[1].split("-")])
for runtime in reversed(ios):
    for d in devices[runtime]:
        if d["name"].startswith("iPhone"):
            print(d["udid"]); sys.exit(0)
sys.exit("no iPhone simulator available")
')
echo "Using simulator ${DEVICE_ID}"

xcodebuild test \
  -project SaigeVault.xcodeproj \
  -scheme SaigeVault \
  -destination "id=${DEVICE_ID}" \
  -resultBundlePath build/TestResults.xcresult \
  CODE_SIGNING_ALLOWED=NO
