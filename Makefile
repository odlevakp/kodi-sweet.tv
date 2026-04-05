ADDON_ID   := plugin.video.sweettv
VERSION    := $(shell date +%Y.%m.%d)
ZIP_NAME   := $(ADDON_ID)-$(VERSION).zip
DIST_DIR   := dist

.PHONY: all build clean release version

all: build

# Build the installable ZIP.
build: clean
	@echo "Building $(ZIP_NAME)..."
	@mkdir -p $(DIST_DIR)
	@gsed -i 's/version="[^"]*"/version="$(VERSION)"/' $(ADDON_ID)/addon.xml
	@zip -r $(DIST_DIR)/$(ZIP_NAME) $(ADDON_ID)/ \
		-x '$(ADDON_ID)/__pycache__/*' \
		-x '$(ADDON_ID)/**/__pycache__/*' \
		-x '$(ADDON_ID)/**/*.pyc' \
		-x '$(ADDON_ID)/**/.DS_Store'
	@echo "Built: $(DIST_DIR)/$(ZIP_NAME)"

# Print the current version.
version:
	@echo $(VERSION)

# Remove build artifacts.
clean:
	@rm -rf $(DIST_DIR)

# Build, commit version bump, tag, push, and create GitHub release.
release: build
	@echo "Creating release $(VERSION)..."
	@git add $(ADDON_ID)/addon.xml
	@git diff --cached --quiet || git commit -m "Release $(VERSION)"
	@git tag -a "v$(VERSION)" -m "Release $(VERSION)" 2>/dev/null || true
	@git push origin main --tags
	@gh release create "v$(VERSION)" \
		$(DIST_DIR)/$(ZIP_NAME) \
		--title "$(ADDON_ID) $(VERSION)" \
		--notes "Sweet.TV Kodi Addon release $(VERSION).\n\nInstall in Kodi via: Settings → Add-ons → Install from ZIP file." \
		--latest
	@echo "Release $(VERSION) published."
