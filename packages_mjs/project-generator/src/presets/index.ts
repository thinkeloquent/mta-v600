/**
 * Preset commands for external tools.
 */

import { execStream, commandExists } from '../utils/exec.js';
import { logger } from '../utils/logger.js';

export interface PresetResult {
  success: boolean;
  error?: string;
}

/**
 * Run degit to clone a repository template.
 * @param repo The repository to clone (e.g., 'user/repo')
 * @param dest The destination directory
 */
export async function degit(repo: string, dest: string): Promise<PresetResult> {
  logger.info(`Cloning ${repo} to ${dest}...`);

  const exitCode = await execStream('npx', ['degit', repo, dest]);

  if (exitCode !== 0) {
    return { success: false, error: `degit failed with exit code ${exitCode}` };
  }

  return { success: true };
}

/**
 * Run npm create vite to scaffold a Vite project.
 * @param projectName The project name
 * @param template The template to use (e.g., 'react-ts')
 */
export async function createVite(projectName: string, template?: string): Promise<PresetResult> {
  logger.info(`Creating Vite project: ${projectName}...`);

  const args = ['vite@latest', projectName];
  if (template) {
    args.push('--template', template);
  }

  const exitCode = await execStream('npm', ['create', ...args]);

  if (exitCode !== 0) {
    return { success: false, error: `create-vite failed with exit code ${exitCode}` };
  }

  return { success: true };
}

/**
 * Run npx create-nx-workspace to create a new Nx workspace.
 * @param workspaceName The workspace name
 * @param preset The preset to use (e.g., 'apps', 'react', 'next')
 */
export async function createNxWorkspace(workspaceName: string, preset?: string): Promise<PresetResult> {
  logger.info(`Creating Nx workspace: ${workspaceName}...`);

  const args = ['create-nx-workspace@latest', workspaceName];
  if (preset) {
    args.push('--preset', preset);
  }

  const exitCode = await execStream('npx', args);

  if (exitCode !== 0) {
    return { success: false, error: `create-nx-workspace failed with exit code ${exitCode}` };
  }

  return { success: true };
}

/**
 * Run npx nx@latest init to add Nx to an existing project.
 */
export async function nxInit(): Promise<PresetResult> {
  logger.info('Adding Nx to existing project...');

  const exitCode = await execStream('npx', ['nx@latest', 'init']);

  if (exitCode !== 0) {
    return { success: false, error: `nx init failed with exit code ${exitCode}` };
  }

  return { success: true };
}

/**
 * Available presets.
 */
export const PRESETS = {
  degit: {
    name: 'degit',
    description: 'Clone a repository template (npx degit user/repo)',
    run: degit,
  },
  vite: {
    name: 'create-vite',
    description: 'Create a Vite project (npm create vite@latest)',
    run: createVite,
  },
  'nx-workspace': {
    name: 'create-nx-workspace',
    description: 'Create an Nx workspace (npx create-nx-workspace@latest)',
    run: createNxWorkspace,
  },
  nx: {
    name: 'nx init',
    description: 'Add Nx to existing project (npx nx@latest init)',
    run: nxInit,
  },
} as const;

export type PresetName = keyof typeof PRESETS;
