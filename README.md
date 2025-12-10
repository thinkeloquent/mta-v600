# MTA PolyNx Orchestrator

PolyNx Orchestrator is a polyglot Nx-powered monorepo that unifies Python and TypeScript/JavaScript services in a single workspace. It includes FastAPI and Fastify backend services, React-based frontend applications, and shared libraries in both languages to enable cross-service code reuse, consistent patterns, and streamlined CI/CD orchestration.

## Quick Start

```bash
# Install dependencies
make install

# Start development servers
make dev
```

## Python Package Management

Local Python packages in `packages_py/` are managed via Poetry path dependencies.

### Sync Local Packages

When adding or removing packages in `packages_py/`, sync with pyproject.toml:

```bash
# Preview changes
python .bin/sync-poetry-local-packages.py --dry-run

# Apply changes
python .bin/sync-poetry-local-packages.py

# Update lock file and install
poetry lock && poetry install
```

### Git Hook Setup

Install a pre-commit hook to ensure packages stay in sync:

```bash
# Install hooks
.bin/git-hook-setup.sh

# Remove hooks
.bin/git-hook-setup.sh --remove
```

The pre-commit hook will block commits if `packages_py/` changes aren't reflected in pyproject.toml.
