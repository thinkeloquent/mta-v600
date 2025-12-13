/**
 * Interactive CLI using @clack/prompts.
 */

import * as p from '@clack/prompts';
import pc from 'picocolors';
import { validateProjectName } from '../core/validators.js';
import type { ProjectType } from '../generators/types.js';

export interface InteractiveAnswers {
  projectType: ProjectType;
  projectName: string;
  options: Record<string, unknown>;
}

/**
 * Project type definitions for interactive selection.
 */
export const PROJECT_TYPES: Array<{
  value: ProjectType;
  label: string;
  hint: string;
}> = [
    { value: 'fastapi', label: 'FastAPI Backend', hint: 'Python REST API with FastAPI' },
    { value: 'fastify', label: 'Fastify Backend', hint: 'Node.js REST API with Fastify' },
    { value: 'frontend', label: 'React Frontend', hint: 'React + Vite + Tailwind' },
    { value: 'react-component', label: 'React Component Package', hint: 'Reusable UI component' },
    { value: 'ts-package', label: 'TypeScript Package', hint: '@internal/* package' },
    { value: 'py-package', label: 'Python Package', hint: 'packages_py/* package' },
    { value: 'health-check-provider', label: 'Health Check Provider', hint: 'Add provider to provider_api_getters' },
  ];

/**
 * Run the interactive project creation flow.
 */
export async function runInteractive(): Promise<InteractiveAnswers | null> {
  p.intro(pc.bgCyan(pc.black(' PolyNx Project Generator ')));

  // Select project type
  const projectType = await p.select({
    message: 'What type of project do you want to create?',
    options: PROJECT_TYPES.map((t) => ({
      value: t.value,
      label: t.label,
      hint: t.hint,
    })),
  });

  if (p.isCancel(projectType)) {
    p.cancel('Operation cancelled.');
    return null;
  }

  // Enter project name
  const projectName = await p.text({
    message: 'What is the project name?',
    placeholder: 'my-project',
    validate: (value) => {
      const result = validateProjectName(value);
      return result === undefined ? undefined : result;
    },
  });

  if (p.isCancel(projectName)) {
    p.cancel('Operation cancelled.');
    return null;
  }

  // Type-specific options
  const options: Record<string, unknown> = {};

  if (projectType === 'fastapi' || projectType === 'fastify') {
    const withFrontend = await p.confirm({
      message: 'Include a frontend app?',
      initialValue: false,
    });

    if (p.isCancel(withFrontend)) {
      p.cancel('Operation cancelled.');
      return null;
    }

    options.withFrontend = withFrontend;
  }

  // Confirm
  const confirmed = await p.confirm({
    message: `Create ${projectType} project "${projectName}"?`,
  });

  if (p.isCancel(confirmed) || !confirmed) {
    p.cancel('Operation cancelled.');
    return null;
  }

  return {
    projectType: projectType as ProjectType,
    projectName: projectName as string,
    options,
  };
}

/**
 * Show a spinner while executing an async task.
 */
export async function withSpinner<T>(
  message: string,
  task: () => Promise<T>
): Promise<T> {
  const spinner = p.spinner();
  spinner.start(message);

  try {
    const result = await task();
    spinner.stop(pc.green('Done'));
    return result;
  } catch (error) {
    spinner.stop(pc.red('Failed'));
    throw error;
  }
}

/**
 * Display post-creation instructions.
 */
export function showPostCreateInstructions(
  projectType: ProjectType,
  projectName: string,
  projectPath: string
): void {
  p.note(
    getPostCreateCommands(projectType, projectName, projectPath),
    'Next steps'
  );

  p.outro(pc.green('Project created successfully!'));
}

/**
 * Get post-creation commands based on project type.
 */
function getPostCreateCommands(
  projectType: ProjectType,
  projectName: string,
  projectPath: string
): string {
  const commands: string[] = [`cd ${projectPath}`];

  switch (projectType) {
    case 'fastapi':
      commands.push('poetry install');
      commands.push('poetry run uvicorn app.main:app --reload');
      break;
    case 'fastify':
      commands.push('pnpm install');
      commands.push('pnpm dev');
      break;
    case 'frontend':
      commands.push('pnpm install');
      commands.push('pnpm dev');
      break;
    case 'react-component':
      commands.push('pnpm install');
      commands.push('pnpm storybook');
      break;
    case 'ts-package':
      commands.push('pnpm install');
      commands.push('pnpm build');
      break;
    case 'py-package':
      commands.push('poetry install');
      commands.push('poetry run pytest');
      break;
  }

  return commands.join('\n');
}
