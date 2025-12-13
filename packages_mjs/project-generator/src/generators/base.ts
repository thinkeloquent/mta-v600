/**
 * Base generator functionality shared by all project generators.
 */

import fs from 'fs-extra';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { processTemplate, validateTemplateDirectory } from '../core/template-engine.js';
import { toSnakeCase } from '../core/naming-conventions.js';
import type { GeneratorOptions, GeneratorResult, ProjectType, ProjectTypeConfig } from './types.js';
import { PROJECT_TYPE_CONFIGS } from './types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Get the root directory of the monorepo.
 */
export function getMonorepoRoot(): string {
  // Navigate from dist/generators to monorepo root
  // dist/generators -> dist -> project-generator -> packages_mjs -> mta-v600 (root)
  return resolve(__dirname, '../../../..');
}

/**
 * Get the templates directory.
 */
export function getTemplatesDir(): string {
  // Templates are embedded in the package at src/templates (not compiled to dist)
  // dist/generators -> dist -> project-generator -> src/templates
  const srcTemplates = resolve(__dirname, '../../src/templates');
  return srcTemplates;
}

/**
 * Get the staged templates directory (for development/migration).
 */
export function getStagedTemplatesDir(): string {
  const root = getMonorepoRoot();
  return join(root, '__STAGE__/mta-v500/tools/project-templates');
}

/**
 * Normalize project name based on project type.
 * - Adds 'app-' prefix for app types if not present
 * - Converts to snake_case for Python projects
 */
export function normalizeProjectName(name: string, projectType: ProjectType): string {
  let normalized = name;

  // Add 'app-' prefix for app types
  if (['fastapi', 'fastify', 'frontend'].includes(projectType)) {
    if (!name.startsWith('app-')) {
      normalized = `app-${name}`;
    }
  }

  return normalized;
}

/**
 * Get the target directory for a project.
 */
export function getTargetDirectory(projectType: ProjectType, projectName: string): string {
  const config = PROJECT_TYPE_CONFIGS[projectType];
  const root = getMonorepoRoot();
  return config.targetDirectory(root, projectName);
}

/**
 * Base generator for all project types.
 */
export async function generateProject(
  projectType: ProjectType,
  options: GeneratorOptions
): Promise<GeneratorResult> {
  const config = PROJECT_TYPE_CONFIGS[projectType];
  const root = getMonorepoRoot();

  // Normalize the project name
  const normalizedName = normalizeProjectName(options.name, projectType);

  // Determine target directory
  const targetDir = options.targetDir || config.targetDirectory(root, normalizedName);

  // Check if target already exists
  const allowExisting = options.allowExisting || config.allowExisting;
  if ((await fs.pathExists(targetDir)) && !allowExisting) {
    return {
      success: false,
      projectPath: targetDir,
      error: `Directory already exists: ${targetDir}`,
    };
  }

  // Find the template directory
  let templateDir = join(getTemplatesDir(), config.templatePath);

  // Fall back to staged templates if embedded templates don't exist
  if (!(await validateTemplateDirectory(templateDir))) {
    templateDir = join(getStagedTemplatesDir(), config.templatePath);
  }

  // Validate template directory exists
  if (!(await validateTemplateDirectory(templateDir))) {
    return {
      success: false,
      projectPath: targetDir,
      error: `Template not found: ${config.templatePath}`,
    };
  }

  try {
    // Create target directory
    await fs.mkdirp(targetDir);

    // Process the template
    await processTemplate({
      sourceDir: templateDir,
      targetDir,
      appName: normalizedName,
      onFileCreate: options.onFileCreate,
    });

    return {
      success: true,
      projectPath: targetDir,
      instructions: getPostGenerationInstructions(projectType, normalizedName, targetDir),
    };
  } catch (error) {
    // Clean up on failure (only if we didn't allow existing, to avoid deleting whole repo)
    if (!allowExisting) {
      await fs.remove(targetDir).catch(() => { });
    }

    return {
      success: false,
      projectPath: targetDir,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Get post-generation instructions for a project type.
 */
function getPostGenerationInstructions(
  projectType: ProjectType,
  projectName: string,
  projectPath: string
): string[] {
  const instructions: string[] = [];

  if (projectType !== 'health-check-provider') {
    instructions.push(`cd ${projectPath}`);
  }

  switch (projectType) {
    case 'fastapi':
      instructions.push('poetry install');
      instructions.push('poetry run uvicorn app.main:app --reload --port 52000');
      break;
    case 'fastify':
      instructions.push('pnpm install');
      instructions.push('pnpm dev');
      break;
    case 'frontend':
      instructions.push('pnpm install');
      instructions.push('pnpm dev');
      break;
    case 'react-component':
      instructions.push('pnpm install');
      instructions.push('pnpm storybook');
      break;
    case 'ts-package':
      instructions.push('pnpm install');
      instructions.push('pnpm build');
      instructions.push('pnpm test');
      break;
    case 'py-package':
      instructions.push('poetry install');
      instructions.push('poetry run pytest');
      break;
    case 'health-check-provider':
      instructions.push(`Files created for provider: ${projectName}`);
      instructions.push('1. Update packages_py/provider_api_getters/src/provider_api_getters/__init__.py to export the new Token class');
      instructions.push('2. Update packages_mjs/provider_api_getters/src/index.mjs to export the new Token class');
      instructions.push(`3. Run 'npm run rebuild' in packages_mjs/provider_api_getters`);
      break;
  }

  return instructions;
}
