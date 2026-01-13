# Scripts - Traverso Analyzer

Utility scripts for development, deployment, and maintenance.

## Available Scripts

### `quick_start.sh` - Quick Setup Script

Automates the initial setup process.

**Features**:
- Checks Python installation
- Offers to create virtual environment
- Installs dependencies
- Runs health check

**Usage**:
```bash
chmod +x scripts/quick_start.sh
./scripts/quick_start.sh
```

### `check_health.py` (in project root)

Comprehensive health check for the environment.

**Usage**:
```bash
python check_health.py
```

Or via Make:
```bash
make verify
```

## Creating Custom Scripts

### Script Template

```bash
#!/bin/bash
# Script description

set -e  # Exit on error

echo "Running my script..."

# Your code here

echo "Done!"
```

### Best Practices

1. **Shebang**: Always include `#!/bin/bash` or `#!/usr/bin/env python3`
2. **Exit on Error**: Use `set -e` in bash scripts
3. **Documentation**: Add comments explaining what the script does
4. **Make Executable**: `chmod +x scripts/your_script.sh`
5. **Test**: Test scripts in a clean environment

## Script Ideas

Feel free to add scripts for:
- Database backup/restore
- Data migration
- Performance profiling
- Batch analysis
- Report generation
- Deployment automation

## Contributing

When adding a new script:
1. Place it in the `scripts/` directory
2. Make it executable
3. Add documentation here
4. Test thoroughly
5. Submit a pull request

---

See `CONTRIBUTING.md` for general contribution guidelines.
