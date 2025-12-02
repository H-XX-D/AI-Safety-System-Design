# Archive Files

This directory contains files that have been archived from the main repository to reduce clutter and improve organization. These files are not essential for the core AI Safety System functionality but may be useful for reference or future development.

## Directory Structure

### External Libraries/
Large external libraries and frameworks that were integrated or evaluated but are not core to the AI Safety System:
- `Agent0/` - Multi-agent framework
- `EasyR1/` - RL training framework
- `ldp/` - Learning Dynamics Platform
- `paper-qa/` - Research paper analysis tool
- `robin/` - Research framework
- `SandboxFusion/` - Sandbox environment
- `verl/` - Verification library
- `verl-tool/` - VERL toolkit

### Old Versions/
Previous or experimental versions of the system:
- `ORKA-v2/` - Older version of ORKA system
- `orka-v2-main/` - Alternative implementation

### Demo Outputs/
Output files from demonstrations and testing:
- `demo_outputs/` - Demo results
- `demo_outputs_doc/` - Documented demo outputs
- `logs/` - System logs
- `training_outputs/` - Training artifacts
- `forensics_snapshots/` - System snapshots

### Research Artifacts/
Research-related files and analysis:
- `patent_search_results.txt` - Patent search results
- `222_AI_COLLABORATION_CONVERSATION copy.txt.html` - Conversation backup
- `analyze_dependencies.py` - Dependency analysis script
- `analyze_problems.py` - Problem analysis script
- `test_worm_usb/` - WORM USB test files
- `path/` - Path-related utilities
- `sidechain/` - Sidechain implementation
- `worm_usb_dir/` - WORM USB directory structure
- `cursor-plan:` - Development planning documents

### Hardware Specific/
Hardware-specific implementations and documentation:
- `esp32/` - ESP32 microcontroller code
- `jetson_nano/` - NVIDIA Jetson Nano deployment
- `edison-client-docs/` - Intel Edison documentation

## Restoration

If you need to restore any archived files, you can move them back to the root directory:

```bash
# Example: Restore Agent0
mv Archive\ Files/External\ Libraries/Agent0 .

# Example: Restore demo outputs
mv Archive\ Files/Demo\ Outputs/demo_outputs .
```

## Notes

- Archived files are still tracked by Git
- This archiving was done to improve repository organization
- Core system functionality remains intact
- Files can be restored if needed for future development

