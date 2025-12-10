/**
 * Template processing engine for project generation.
 * Handles copying templates, replacing placeholders, and processing .tmpl files.
 */

import fs from 'fs-extra';
import { join, basename, dirname } from 'node:path';
import { replacePlaceholders } from './naming-conventions.js';

/**
 * Options for template processing.
 */
export interface TemplateOptions {
  /** The source template directory */
  sourceDir: string;
  /** The target directory for the generated project */
  targetDir: string;
  /** The project name (kebab-case) */
  appName: string;
  /** Callback for logging file creation */
  onFileCreate?: (filePath: string) => void;
  /** Directories to skip during copy */
  skipDirs?: string[];
  /** Files to skip during copy */
  skipFiles?: string[];
}

/**
 * Default directories to skip when copying templates.
 */
export const DEFAULT_SKIP_DIRS = [
  'node_modules',
  'dist',
  'build',
  'venv',
  '.venv',
  '__pycache__',
  '.pytest_cache',
  '.git',
  '.idea',
  '.vscode',
  'coverage',
];

/**
 * Default files to skip when copying templates.
 */
export const DEFAULT_SKIP_FILES = [
  '.DS_Store',
  'Thumbs.db',
  '.gitkeep',
];

/**
 * Process a template directory and copy it to the target location.
 * - Replaces placeholders in file contents and filenames
 * - Removes .tmpl extension from files
 * - Skips specified directories and files
 */
export async function processTemplate(options: TemplateOptions): Promise<void> {
  const {
    sourceDir,
    targetDir,
    appName,
    onFileCreate,
    skipDirs = DEFAULT_SKIP_DIRS,
    skipFiles = DEFAULT_SKIP_FILES,
  } = options;

  await copyTemplateRecursive(sourceDir, targetDir, appName, {
    onFileCreate,
    skipDirs: new Set(skipDirs),
    skipFiles: new Set(skipFiles),
  });
}

interface CopyContext {
  onFileCreate?: (filePath: string) => void;
  skipDirs: Set<string>;
  skipFiles: Set<string>;
}

/**
 * Recursively copy and process template files.
 */
async function copyTemplateRecursive(
  srcDir: string,
  destDir: string,
  appName: string,
  context: CopyContext
): Promise<void> {
  const entries = await fs.readdir(srcDir);

  for (const entry of entries) {
    const srcPath = join(srcDir, entry);
    const stat = await fs.stat(srcPath);

    // Skip directories
    if (stat.isDirectory() && context.skipDirs.has(entry)) {
      continue;
    }

    // Skip files
    if (stat.isFile() && context.skipFiles.has(entry)) {
      continue;
    }

    // Process entry name
    let destEntry = entry;

    // Remove .tmpl extension
    if (entry.endsWith('.tmpl')) {
      destEntry = entry.slice(0, -5);
    }

    // Replace placeholders in filename
    destEntry = replacePlaceholders(destEntry, appName);

    const destPath = join(destDir, destEntry);

    if (stat.isDirectory()) {
      // Create directory and recurse
      await fs.mkdirp(destPath);
      await copyTemplateRecursive(srcPath, destPath, appName, context);
    } else {
      // Process file
      const content = await fs.readFile(srcPath, 'utf-8');
      const processedContent = replacePlaceholders(content, appName);

      // Ensure parent directory exists
      await fs.mkdirp(dirname(destPath));
      await fs.writeFile(destPath, processedContent);

      // Notify about file creation
      if (context.onFileCreate) {
        context.onFileCreate(destPath);
      }
    }
  }
}

/**
 * Copy a single file with placeholder replacement.
 */
export async function copyFileWithPlaceholders(
  srcPath: string,
  destPath: string,
  appName: string
): Promise<void> {
  const content = await fs.readFile(srcPath, 'utf-8');
  const processedContent = replacePlaceholders(content, appName);
  await fs.mkdirp(dirname(destPath));
  await fs.writeFile(destPath, processedContent);
}

/**
 * Check if a template directory exists and is valid.
 */
export async function validateTemplateDirectory(templateDir: string): Promise<boolean> {
  try {
    const stat = await fs.stat(templateDir);
    return stat.isDirectory();
  } catch {
    return false;
  }
}
