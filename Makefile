ADDON_ID   := plugin.video.sweettv
REPO_ID    := repository.sweettv
VERSION    := $(shell gsed -n '/^       version=/s/.*version="\([^"]*\)".*/\1/p' $(ADDON_ID)/addon.xml)
ZIP_NAME   := $(ADDON_ID)-$(VERSION).zip
REPO_ZIP   := $(REPO_ID)-1.0.0.zip
DIST_DIR   := dist

.PHONY: all build clean release version repo

all: build

# Build the installable addon ZIP.
build: clean
	@echo "Building $(ZIP_NAME)..."
	@mkdir -p $(DIST_DIR)
	@gsed -i '/^       version="/s/version="[^"]*"/version="$(VERSION)"/' $(ADDON_ID)/addon.xml
	@zip -r $(DIST_DIR)/$(ZIP_NAME) $(ADDON_ID)/ \
		-x '$(ADDON_ID)/__pycache__/*' \
		-x '$(ADDON_ID)/**/__pycache__/*' \
		-x '$(ADDON_ID)/**/*.pyc' \
		-x '$(ADDON_ID)/**/.DS_Store'
	@echo "Built: $(DIST_DIR)/$(ZIP_NAME)"

# Build the repository addon ZIP.
repo:
	@echo "Building $(REPO_ZIP)..."
	@mkdir -p $(DIST_DIR)
	@zip -r $(DIST_DIR)/$(REPO_ZIP) $(REPO_ID)/
	@echo "Built: $(DIST_DIR)/$(REPO_ZIP)"

# Generate repo/addons.xml and repo/addons.xml.md5 from current addon.xml files.
repo-index:
	@echo "Generating repo/addons.xml..."
	@echo '<?xml version="1.0" encoding="UTF-8"?>' > repo/addons.xml
	@echo '<addons>' >> repo/addons.xml
	@gsed -n '/<addon/,/<\/addon>/p' $(ADDON_ID)/addon.xml >> repo/addons.xml
	@gsed -n '/<addon/,/<\/addon>/p' $(REPO_ID)/addon.xml >> repo/addons.xml
	@echo '</addons>' >> repo/addons.xml
	@md5sum repo/addons.xml | cut -d' ' -f1 > repo/addons.xml.md5
	@echo "Generated repo/addons.xml (md5: $$(cat repo/addons.xml.md5))"

# Print the current version.
version:
	@echo $(VERSION)

# Remove build artifacts.
clean:
	@rm -rf $(DIST_DIR)

# Build, update repo index, commit, tag, push, and create GitHub release.
release: build repo repo-index
	@echo "Creating release $(VERSION)..."
	@git add $(ADDON_ID)/addon.xml repo/addons.xml repo/addons.xml.md5
	@git diff --cached --quiet || git commit -m "Release $(VERSION)"
	@git tag -a "v$(VERSION)" -m "Release $(VERSION)" 2>/dev/null || true
	@git push origin main --tags
	@gh release create "v$(VERSION)" \
		$(DIST_DIR)/$(ZIP_NAME) \
		$(DIST_DIR)/$(REPO_ZIP) \
		--title "$(ADDON_ID) $(VERSION)" \
		--notes "$$(printf 'Sweet.TV Kodi Addon release $(VERSION).\n\n**First time?** Download `$(REPO_ZIP)`, install it in Kodi via Settings → Add-ons → Install from ZIP file, then install Sweet.TV from the repository. Future updates will be automatic.\n\n**Already have the repo?** Update will be picked up automatically by Kodi.')" \
		--latest
	@echo "Release $(VERSION) published."
