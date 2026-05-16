# Shadow Self-Upgrade Workflow for ARIA

This document describes a safe methodology for upgrading ARIA's own codebase while maintaining system stability.

## v1.6 case study — applied successfully 2026-05-16

The v1.6 comeback release was built and validated using this exact workflow:

1. **Shadow:** all 9 architectural changes (mode router, FSM, delta context, recall, tool guards, loop guard, verify_goal, fetch_api_spec, acceptance_test, runtime validator, relation graph) were implemented directly in the installed pipx venv as the experimentation surface.
2. **Validated live:** burn-in test in `/home/sumit/projects/aria-testing/` with `nemotron-3-super:cloud`. All gates fired in real flows: FSM blocked rogue `write_file`, tool guard blocked bare `pip install`, verify_goal + acceptance_test ran on every code-generating task, no-go list honored. See `ARIA_testing_logs.txt` for full transcript.
3. **Promoted:** changes were rsync'd from venv to source tree at `/home/sumit/ARIA/source_v1.6/ARIA-backup-20260511/`. Cross-version check confirmed 1.6.0 across `pyproject.toml`, `aria/__init__.py`, `aria/ui/banner.py`.
4. **User memory preserved:** `~/.aria/memory.json`, `config.json`, `checkpoints/` untouched. No migration needed.
5. **Rollback option:** previous source zip retained in `~/project_vault/aria-developer-20260513.zip`.

Lesson: working directly in the installed venv (instead of a separate shadow dir) is acceptable for solo-developer workflow when source-tree sync is the final promotion step. Faster iteration, same safety, as long as the sync-to-source step isn't skipped.

## Overview
The shadow self-upgrade approach allows ARIA to experiment with and validate upgrades in an isolated environment before promoting changes to the active codebase. This minimizes risk of breaking the running system.

## Workflow Steps

### 1. Preparation
- Create a backup of the current stable codebase
- Create a shadow workspace (copy of current codebase)
- Ensure the backup is stored safely outside the working directories

### 2. Isolation
- All upgrade work occurs exclusively in the shadow workspace
- The original codebase remains untouched and continues running normally
- No filesystem modifications are made to the active system during experimentation

### 3. Experimentation & Validation
- Make desired changes (dependency updates, feature enhancements, bug fixes) in shadow workspace
- Run comprehensive tests:
  - Unit tests for modified components
  - Integration tests for workflow validation
  - Manual verification of critical functions
- Validate using the shadow workspace's own ARIA instance:
  - Install changes in shadow workspace: `.venv/bin/pip install -e .`
  - Test functionality: `aria --help`, `aria "simple query"`, etc.
  - Verify no regressions in core capabilities

### 4. Review & Approval
- Present detailed changes and test results for human review
- Obtain explicit approval before proceeding to promotion
- Review includes:
  - Diff summary of all changes
  - Test coverage and results
  - Risk assessment
  - Rollback procedure confirmation

### 5. Promotion
Upon approval:
- Option A: Replace specific components
  - Copy validated files from shadow to active codebase
  - Restart ARIA to load updated components
- Option B: Full cutover
  - Rename active codebase to `aria-backup-previous`
  - Rename shadow workspace to `aria` (active)
  - Restart ARIA from the new active directory
- Option C: Reinstall
  - Install shadow workspace as package: `cd aria-shadow && .venv/bin/pip install -e .`
  - This updates the installed package while keeping source intact

### 6. Validation After Promotion
- Run smoke tests to ensure basic functionality works
- Verify memory and configurations are intact
- Confirm the upgraded system behaves as expected

### 7. Rollback Procedure (if needed)
- If issues arise post-promotion:
  - Stop the upgraded ARIA instance
  - Restore from backup or switch back to previous version
  - For Option A: Restore specific files from backup
  - For Option B: Swap directory names back
  - For Option C: Reinstall previous version or restore backup

## Safety Features
- **Zero-downtime experimentation**: Active system unaffected during upgrades
- **Instant rollback**: Multiple recovery points available
- **Tested changes**: All modifications validated before promotion
- **Human oversight**: Explicit approval required for promotion
- **Backup preservation**: Original codebase safely stored

## Application to Specific Components

### Dependency Updates
1. Modify `pyproject.toml` in shadow workspace
2. Reinstall dependencies: `.venv/bin/pip install -e .`
3. Run test suite to ensure compatibility
4. Promote updated dependencies

### Core Component Enhancements (e.g., AST Validator)
1. Implement changes in shadow workspace
2. Run enhanced unit tests
3. Validate with integration scenarios
4. Promote only after full test suite passes

### Workflow Improvements
1. Test new features in isolation
2. Verify they don't break existing functionality
3. Promote after validation

## Memory and State Considerations
- User memory (`~/.aria/`) remains shared and unaffected
- Project-specific memory remains intact
- Configuration files (`~/.aria/config.json`) persist
- Only source code and installed packages change during upgrade

## Example: Safe AST Validator Upgrade
```
# Preparation
cp -r /home/sumit/ARIA /home/sumit/ARIA-backup-$(date +%Y%m%d%H%M%S)
rsync -av /home/sumit/ARIA/ /home/sumit/aria-shadow/ --exclude={.git,aria-backup-*,aria-shadow}

# Work in shadow
cd /home/sumit/aria-shadow
# Edit ast_validator/rules/removed_nodes.py
# Add enhanced validation rules
# Update tests/unit/test_ast_validator_enhanced.py

# Validate
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests/unit/ -v
aria "Test the AST validator with Python 3.14 code"

# After approval: Promote
# Option B (full cutover):
mv /home/sumit/ARIA /home/sumit/ARIA-pre-upgrade-$(date +%Y%m%d%H%M%S)
mv /home/sumit/aria-shadow /home/sumit/ARIA
aria  # Restart from new active directory
```