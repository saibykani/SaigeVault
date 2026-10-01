# Saige Vault iOS — run on macOS with Xcode 16+.
SHELL := /bin/bash
SCHEME := SaigeVault
PROJECT := SaigeVault.xcodeproj
SIM ?= platform=iOS Simulator,name=iPhone 16
ARCHIVE := build/SaigeVault.xcarchive

.PHONY: bootstrap project test build archive ipa-dev ipa-adhoc clean

bootstrap:
	@command -v xcodegen >/dev/null || brew install xcodegen
	@test -f Config/Local.xcconfig || cp Config/Local.xcconfig.example Config/Local.xcconfig
	$(MAKE) project

project:
	xcodegen generate

test: project
	xcodebuild test -project $(PROJECT) -scheme $(SCHEME) -destination '$(SIM)' \
		CODE_SIGNING_ALLOWED=NO

build: project
	xcodebuild build -project $(PROJECT) -scheme $(SCHEME) -destination 'generic/platform=iOS Simulator' \
		CODE_SIGNING_ALLOWED=NO

archive: project
	xcodebuild archive -project $(PROJECT) -scheme $(SCHEME) -configuration Release \
		-destination 'generic/platform=iOS' -archivePath $(ARCHIVE) -allowProvisioningUpdates

ipa-dev: archive
	xcodebuild -exportArchive -archivePath $(ARCHIVE) -exportPath build/ipa-dev \
		-exportOptionsPlist ExportOptions/Development.plist -allowProvisioningUpdates

ipa-adhoc: archive
	xcodebuild -exportArchive -archivePath $(ARCHIVE) -exportPath build/ipa-adhoc \
		-exportOptionsPlist ExportOptions/AdHoc.plist -allowProvisioningUpdates

clean:
	rm -rf build $(PROJECT)
